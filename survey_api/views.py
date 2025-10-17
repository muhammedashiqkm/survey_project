import logging
from collections import defaultdict
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    College, Student, Question, Option, Section, StudentResponse, StudentSectionResult
)
from .serializers import SurveySerializer, StudentRegistrationSerializer, SubmissionSerializer
from rest_framework.exceptions import ValidationError
from django.db.models import Prefetch, Count
from django.utils import timezone

logger = logging.getLogger('survey_api')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_student(request):
    serializer = StudentRegistrationSerializer(data=request.data, context={'request': request})
    try:
        serializer.is_valid(raise_exception=True)
        student = serializer.save()

        logger.info(f"Student {student.id} registered for college {student.college.name}.")
        return Response({"message": "Student registered successfully", "student_id": student.id}, status=status.HTTP_201_CREATED)
    except ValidationError as e:

        logger.warning(f"Student registration failed validation: {e.detail}")
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_survey(request, college_name):
    
    logger.debug(f"Fetching survey for college: {college_name}")
    college = get_object_or_404(
        College.objects.prefetch_related(
            Prefetch('categories__sections__questions__options')
        ),
        name__iexact=college_name
    )
    serializer = SurveySerializer(college)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_responses(request, college_name, student_id):
    submission_serializer = SubmissionSerializer(data=request.data)
    try:
        submission_serializer.is_valid(raise_exception=True)
        responses_data = submission_serializer.validated_data['responses']
        college = get_object_or_404(College, name__iexact=college_name)
        student = get_object_or_404(Student, student_id=student_id, college=college)

        question_ids = {r['question_id'] for r in responses_data}
        option_ids = {r['selected_option_id'] for r in responses_data}
        questions_qs = Question.objects.filter(id__in=question_ids, section__category__college=college)\
            .select_related('section__category')
        options_qs = Option.objects.filter(id__in=option_ids).select_related('question__section__category')
        questions_map = {q.id: q for q in questions_qs}
        options_map = {o.id: o for o in options_qs}

        missing_questions = question_ids - set(questions_map.keys())
        missing_options = option_ids - set(options_map.keys())
        if missing_questions or missing_options:
            return Response({
                "error": "Invalid question_id or selected_option_id referenced",
                "missing_questions": list(missing_questions),
                "missing_options": list(missing_options)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        existing_responses = StudentResponse.objects.filter(
            student=student,
            question_id__in=question_ids
        )
        existing_responses_map = {resp.question_id: resp for resp in existing_responses}
        responses_to_create = []
        responses_to_update = []
        
        objective_sections_touched = set()

        for r_data in responses_data:
            qid = r_data['question_id']
            oid = r_data['selected_option_id']
            question = questions_map[qid]
            option = options_map[oid]
            if option.question_id != qid:
                return Response({"error": f"Option {oid} does not belong to question {qid}"}, status=status.HTTP_400_BAD_REQUEST)
            if qid in existing_responses_map:
                response_obj = existing_responses_map[qid]
                if response_obj.selected_option_id != oid:
                    response_obj.selected_option_id = oid
                    response_obj.submitted_at = timezone.now()
                    responses_to_update.append(response_obj)
            else:
                responses_to_create.append(
                    StudentResponse(student=student, question=question, selected_option=option)
                )
            
            if question.section.category.has_correct_answers:
                objective_sections_touched.add(question.section_id)
        
        with transaction.atomic():
            if responses_to_update:
                StudentResponse.objects.bulk_update(responses_to_update, ['selected_option_id', 'submitted_at'])
            if responses_to_create:
                StudentResponse.objects.bulk_create(responses_to_create)
            
            for section_id in objective_sections_touched:
                total_marks = StudentResponse.objects.filter(
                    student=student,
                    question__section_id=section_id,
                    selected_option__is_correct=True
                ).count()
                
                StudentSectionResult.objects.update_or_create(
                    student=student,
                    section_id=section_id,
                    defaults={'total_marks': total_marks}
                )

        logger.info(f"Responses submitted for student {student_id}. {len(responses_to_create)} created, {len(responses_to_update)} updated.")
        return Response({"message": "Responses submitted successfully"}, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    except ObjectDoesNotExist as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    except IntegrityError:
        logger.error(f"IntegrityError during response submission for student {student_id}, potential race condition.", exc_info=True)
        return Response({"error": "A database conflict occurred. Please try again."}, status=status.HTTP_409_CONFLICT)
    except Exception as e:
        logger.error(f"Unexpected error in submit_responses for student {student_id}: {e}", exc_info=True)
        return Response({"error": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_results(request, college_name, student_id):

    logger.debug(f"Fetching results for student {student_id} at {college_name}")
    college = get_object_or_404(College, name__iexact=college_name)
    student = get_object_or_404(Student, student_id=student_id, college=college)
    results_by_category = defaultdict(lambda: {"objective": [], "subjective": []})

    marks_results = StudentSectionResult.objects.filter(student=student)\
        .select_related('section__category')\
        .annotate(total_section_questions=Count('section__questions'))

    for result in marks_results:
        category_name = result.section.category.name
        results_by_category[category_name]["objective"].append({
            "section": result.section.name,
            "result_type": "marks",
            "total_mark": result.total_section_questions,
            "student_score": result.total_marks
        })

    subjective_responses = StudentResponse.objects.filter(
        student=student, question__section__category__has_correct_answers=False
    ).select_related('question__section__category', 'selected_option')

    responses_by_section_and_category = defaultdict(list)
    for response in subjective_responses:
        cat = response.question.section.category.name
        sec = response.question.section.name
        responses_by_section_and_category[(cat, sec)].append({
            "question": response.question.text,
            "selected_option": response.selected_option.text
        })

    for (category_name, section_name), responses in responses_by_section_and_category.items():
        results_by_category[category_name]["subjective"].append({
            "section": section_name,
            "result_type": "subjective",
            "responses": responses
        })

    final_response = {
        "student_name": student.name,
        "student_id": student.student_id,
        "results": []
    }

    for category_name, sections in results_by_category.items():
        category_data = {
            "category": category_name,
            "sections": sections["objective"] + sections["subjective"]
        }
        final_response["results"].append(category_data)
    
    logger.info(f"Successfully generated results for student {student_id} at {college_name}.")
    return Response(final_response)