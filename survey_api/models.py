from django.db import models, transaction
from django.urls import reverse
from django.contrib.auth.models import User
from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone




class College(models.Model):
    name = models.CharField(max_length=200, unique=True, db_index=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('admin:survey_api_college_change', args=[str(self.id)])
    
class CollegeAdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    college = models.ForeignKey(College, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} - {self.college.name}"


class Category(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='categories', db_index=True)
    name = models.CharField(max_length=255)
    has_correct_answers = models.BooleanField(default=False, help_text="Check if questions in this category have correct answers.")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.college.name})"

    def get_absolute_url(self):
        return reverse('admin:survey_api_category_change', args=[str(self.id)])


class SubjectiveOptionTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., '5-Point Likert Scale'")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('admin:survey_api_subjectiveoptiontemplate_change', args=[str(self.id)])


class Section(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='sections', db_index=True)
    name = models.CharField(max_length=255)
    subjective_option_template = models.ForeignKey(SubjectiveOptionTemplate, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.category.name} - {self.category.college.name})"

    def get_absolute_url(self):
        return reverse('admin:survey_api_section_change', args=[str(self.id)])


class SubjectiveOption(models.Model):
    template = models.ForeignKey(SubjectiveOptionTemplate, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text


class Question(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='questions', db_index=True)
    text = models.TextField()

    def __str__(self):
        return self.text[:60]



class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options', db_index=True)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text
    
@receiver(post_save, sender=Question)
def create_default_options(sender, instance, created, **kwargs):
    """
    Automatically creates options for subjective questions based on the section template.
    Triggered only when a new Question is created.
    """
    if created and not instance.section.category.has_correct_answers:
        template = instance.section.subjective_option_template
        if template:
            option_qs = template.options.all()
            if option_qs.exists():
                Option.objects.bulk_create([
                    Option(question=instance, text=o.text) for o in option_qs
                ])
    

class Student(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='students', db_index=True)
    student_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['college', 'student_id'], name='unique_college_studentid')
        ]
        indexes = [
            models.Index(fields=['college', 'student_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.student_id})"

    def get_absolute_url(self):
        return reverse('admin:survey_api_student_change', args=[str(self.id)])


class StudentResponse(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='responses', db_index=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, db_index=True)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'question'], name='unique_student_question_response')
        ]

    def __str__(self):
        return f"Response by {self.student.name} for question {self.question.id}"


class StudentSectionResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='section_results', db_index=True)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, db_index=True)
    total_marks = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'section'], name='unique_student_section_result')
        ]

    def __str__(self):
        return f"Result for {self.student.name} in {self.section.name}: {self.total_marks} marks"