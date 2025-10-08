from django.urls import path
from .views import (
    register_student, 
    get_survey, 
    submit_responses,
    get_student_results
)

urlpatterns = [
    path('register-student/', register_student, name='register-student'),
    
    path('questions/<str:college_name>/', get_survey, name='get-survey'),
    
    path('submit-answers/<str:college_name>/<str:student_id>/', submit_responses, name='submit-responses'),
    
    path('students/<str:college_name>/<str:student_id>/results/', get_student_results, name='get-results'),
]