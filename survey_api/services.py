from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    Student, College, Question, Option, 
    StudentResponse, StudentSectionResult
)

class SurveySubmissionService:
    """
    Service class to handle the business logic of submitting survey responses.
    Encapsulates validation, bulk database operations, and score calculation.
    """
    def __init__(self, college_name, student_id, responses_data):
        self.college_name = college_name
        self.student_id = student_id
        self.responses_data = responses_data
        self.college = None
        self.student = None

    def process_submission(self):
        """
        Main method to execute the submission process.
        Returns a tuple: (created_count, updated_count)
        """
        # 1. Fetch Context (Fail fast if not found)
        self.college = get_object_or_404(College, name__iexact=self.college_name)
        self.student = get_object_or_404(Student, student_id=self.student_id, college=self.college)

        # 2. Optimization: Gather all IDs to fetch data in bulk
        question_ids = {r['question_id'] for r in self.responses_data}
        option_ids = {r['selected_option_id'] for r in self.responses_data}

        # 3. Bulk Fetching (Reduces N queries to 2)
        # Fetch questions only for this college to ensure security context
        questions_qs = Question.objects.filter(
            id__in=question_ids, 
            section__category__college=self.college
        ).select_related('section__category')
        
        options_qs = Option.objects.filter(
            id__in=option_ids
        ).select_related('question')

        # Create lookup maps for O(1) access
        questions_map = {q.id: q for q in questions_qs}
        options_map = {o.id: o for o in options_qs}

        # 4. Validation
        self._validate_completeness(question_ids, option_ids, questions_map, options_map)

        # 5. Prepare DB Objects
        existing_responses = StudentResponse.objects.filter(
            student=self.student, 
            question_id__in=question_ids
        )
        existing_responses_map = {resp.question_id: resp for resp in existing_responses}
        
        responses_to_create = []
        responses_to_update = []
        objective_sections_touched = set()

        for r_data in self.responses_data:
            qid = r_data['question_id']
            oid = r_data['selected_option_id']
            
            question = questions_map[qid]
            option = options_map[oid]

            # Integrity Check: Ensure the option actually belongs to the question
            if option.question_id != qid:
                raise ValueError(f"Integrity Error: Option {oid} does not belong to question {qid}")

            # Logic: Update if exists, Create if new
            if qid in existing_responses_map:
                response_obj = existing_responses_map[qid]
                # Only update if the choice actually changed
                if response_obj.selected_option_id != oid:
                    response_obj.selected_option_id = oid
                    response_obj.submitted_at = timezone.now()
                    responses_to_update.append(response_obj)
            else:
                responses_to_create.append(
                    StudentResponse(student=self.student, question=question, selected_option=option)
                )
            
            # Track sections that need score recalculation (Objective only)
            if question.section.category.has_correct_answers:
                objective_sections_touched.add(question.section_id)

        # 6. Atomic Execution
        with transaction.atomic():
            if responses_to_update:
                StudentResponse.objects.bulk_update(responses_to_update, ['selected_option_id', 'submitted_at'])
            
            if responses_to_create:
                StudentResponse.objects.bulk_create(responses_to_create)
            
            # Recalculate marks only for sections that were modified
            if objective_sections_touched:
                self._recalculate_marks(objective_sections_touched)

        return len(responses_to_create), len(responses_to_update)

    def _validate_completeness(self, q_ids, o_ids, q_map, o_map):
        """Ensure all requested IDs actually exist in the DB/Context."""
        missing_questions = q_ids - set(q_map.keys())
        missing_options = o_ids - set(o_map.keys())
        
        if missing_questions or missing_options:
            raise ValueError(
                f"Invalid IDs referenced. "
                f"Missing/Unauthorized Questions: {list(missing_questions)}, "
                f"Missing Options: {list(missing_options)}"
            )

    def _recalculate_marks(self, section_ids):
        """
        Recalculate marks for touched sections using Aggregation 
        (Reduces N*2 queries to 1 read + N writes)
        """
        # 1. Calculate scores for ALL touched sections in ONE query
        stats = StudentResponse.objects.filter(
            student=self.student,
            question__section_id__in=section_ids,
            selected_option__is_correct=True
        ).values('question__section_id').annotate(
            score=Count('id')
        )
        scores_map = {item['question__section_id']: item['score'] for item in stats}

        for section_id in section_ids:
            score = scores_map.get(section_id, 0)
            
            StudentSectionResult.objects.update_or_create(
                student=self.student,
                section_id=section_id,
                defaults={'total_marks': score}
            )