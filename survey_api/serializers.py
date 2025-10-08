from rest_framework import serializers
from django.db import transaction, IntegrityError
from .models import (
    College, Category, Section, Question, Option, Student, StudentResponse, StudentSectionResult
)


class StudentRegistrationSerializer(serializers.ModelSerializer):
    college_name = serializers.CharField(write_only=True)

    class Meta:
        model = Student
        fields = ['student_id', 'name', 'college_name']

    def validate_college_name(self, value):
        try:
            college = College.objects.get(name__iexact=value.strip())
        except College.DoesNotExist:
            raise serializers.ValidationError(f"College with name '{value}' does not exist.")
        self.context['college_instance'] = college
        return value

    def create(self, validated_data):
        college = self.context.get('college_instance')
        student_id = validated_data.get('student_id')
        name = validated_data.get('name')

        try:
            with transaction.atomic():
                student, created = Student.objects.get_or_create(
                    college=college,
                    student_id=student_id,
                    defaults={'name': name}
                )
                if not created:
                    raise serializers.ValidationError(f"A student with ID '{student_id}' already exists in this college.")
                return student
        except IntegrityError:
            raise serializers.ValidationError("Unable to create student due to concurrent operation. Try again.")


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'options']


class SectionSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['name', 'questions']


class CategorySerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['name', 'has_correct_answers', 'sections']


class SurveySerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    college_name = serializers.CharField(source='name')

    class Meta:
        model = College
        fields = ['college_name', 'categories']



class ResponseItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    selected_option_id = serializers.IntegerField()

class SubmissionSerializer(serializers.Serializer):
    responses = ResponseItemSerializer(many=True, allow_empty=False)