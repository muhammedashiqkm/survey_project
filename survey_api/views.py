import logging
from collections import defaultdict
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Count
from rest_framework.exceptions import ValidationError

# Imports from your project
from .models import (
    College, Student, Question, Option, Section, 
    StudentResponse, StudentSectionResult
)
from .serializers import (
    SurveySerializer, StudentRegistrationSerializer, SubmissionSerializer
)
# IMPORT THE NEW SERVICE
from .services import SurveySubmissionService

logger = logging.getLogger('survey_api')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_student(request):
    """
    Registers a student to a specific college.
    """
    serializer = StudentRegistrationSerializer(data=request.data, context={'request': request})
    try:
        serializer.is_valid(raise_exception=True)
        student = serializer.save()

        logger.info(f"Student {student.id} registered for college {student.college.name}.")
        return Response(
            {"message": "Student registered successfully", "student_id": student.id}, 
            status=status.HTTP_201_CREATED
        )
    except ValidationError as e:
        logger.warning(f"Student registration failed validation: {e.detail}")
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_survey(request, college_name):
    """
    Fetches the full survey structure for a college.
    Optimized with prefetch_related to prevent N+1 queries.
    """
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
    """
    Handles the submission of survey answers.
    Delegates complex logic to SurveySubmissionService.
    """
    submission_serializer = SubmissionSerializer(data=request.data)
    try:
        # 1. Validate format
        submission_serializer.is_valid(raise_exception=True)
        responses_data = submission_serializer.validated_data['responses']

        # 2. Initialize Service
        service = SurveySubmissionService(college_name, student_id, responses_data)
        
        # 3. Execute Logic (Process Submission)
        created_count, updated_count = service.process_submission()

        logger.info(f"Responses submitted for student {student_id}. {created_count} created, {updated_count} updated.")
        return Response({"message": "Responses submitted successfully"}, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    
    except ValueError as e:
        # Catches logical errors from the service (e.g., option not belonging to question)
        logger.warning(f"Validation error during submission for {student_id}: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    except ObjectDoesNotExist:
        return Response({"error": "Student or College not found."}, status=status.HTTP_404_NOT_FOUND)
    
    except IntegrityError:
        logger.error(f"IntegrityError during response submission for student {student_id}.", exc_info=True)
        return Response({"error": "A database conflict occurred. Please try again."}, status=status.HTTP_409_CONFLICT)
    
    except Exception as e:
        logger.error(f"Unexpected error in submit_responses for student {student_id}: {e}", exc_info=True)
        return Response({"error": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_results(request, college_name, student_id):
    """
    Aggregates results for a specific student.
    Separates Objective (marks) from Subjective (text responses).
    """
    logger.debug(f"Fetching results for student {student_id} at {college_name}")
    
    college = get_object_or_404(College, name__iexact=college_name)
    student = get_object_or_404(Student, student_id=student_id, college=college)
    
    results_by_category = defaultdict(lambda: {"objective": [], "subjective": []})

    # 1. Fetch Objective Marks
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

    # 2. Fetch Subjective Responses
    # Optimized with select_related to grab all hierarchy levels in one go
    subjective_responses = StudentResponse.objects.filter(
        student=student, 
        question__section__category__has_correct_answers=False
    ).select_related('question__section__category', 'selected_option')

    # Group subjective responses in Python to avoid complex SQL grouping
    responses_by_section_and_category = defaultdict(list)
    for response in subjective_responses:
        cat = response.question.section.category.name
        sec = response.question.section.name
        responses_by_section_and_category[(cat, sec)].append({
            "question": response.question.text,
            "selected_option": response.selected_option.text
        })

    # Transform subjective groupings into final JSON structure
    for (category_name, section_name), responses in responses_by_section_and_category.items():
        results_by_category[category_name]["subjective"].append({
            "section": section_name,
            "result_type": "subjective",
            "responses": responses
        })

    # Construct Final Response
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