# survey_api/forms.py
from django import forms
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import StudentResponse, StudentSectionResult

class StudentResponseAdminForm(forms.ModelForm):
    class Meta:
        model = StudentResponse
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        question = cleaned_data.get("question")

        if student and question:
            if student.college != question.section.category.college:
                raise ValidationError("Error: The selected student and question belong to different colleges.")
        return cleaned_data

class StudentSectionResultAdminForm(forms.ModelForm):
    class Meta:
        model = StudentSectionResult
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        section = cleaned_data.get("section")

        if student and section:
            if student.college != section.category.college:
                raise ValidationError("Error: The selected student and section belong to different colleges.")
            
        if not section.category.has_correct_answers:
                raise ValidationError(
                    "Marks cannot be assigned. The selected section belongs to a category that does not have marks (e.g., a subjective survey)."
                )
        
        return cleaned_data

class OptionInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        question = self.instance

        # The form can't proceed if a section hasn't been selected yet.
        if not hasattr(question, 'section'):
             return
        
        is_mark_category = question.section.category.has_correct_answers
        has_template = question.section.subjective_option_template is not None

        total_options_count = 0
        correct_answers_count = 0

        for form in self.forms:
            # Skip forms that are slated for deletion
            if self.can_delete and self._should_delete_form(form):
                continue
            
            # Skip empty extra forms that haven't been touched
            if not form.has_changed():
                continue

            total_options_count += 1
            
            if form.cleaned_data.get('is_correct', False):
                correct_answers_count += 1
        
        # Apply validation rules based on the conditions
        if is_mark_category:
            if total_options_count == 0:
                raise ValidationError('You must add at least one answer option for a question in a mark category.')
            if correct_answers_count == 0:
                raise ValidationError('You must select one correct answer for this question.')
            if correct_answers_count > 1:
                raise ValidationError('You can only select one correct answer for this question.')

        elif not is_mark_category and not has_template:
            if total_options_count == 0:
                raise ValidationError('For subjective questions without a option template, you must add the answer options manually.')