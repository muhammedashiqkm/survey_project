# filename: seed_data.py
import os
import django
import random
from faker import Faker

# --- IMPORTANT ---
# Change 'myproject.settings' to your project's settings module.
# This is crucial for the script to know about your Django project.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'survey_project.settings')
django.setup()

# Now you can import your models
from survey_api.models import (
    College, Category, SubjectiveOptionTemplate, SubjectiveOption,
    Section, Question, Option, Student, StudentResponse
)
# --- IMPORTANT ---
# Change 'yourapp' to the name of the app where your models.py is located.


# Initialize Faker
fake = Faker()

# --- Configuration ---
# You can change these numbers to create more or less data.
NUM_COLLEGES = 5
NUM_STUDENTS_PER_COLLEGE = 100
NUM_QUESTIONS_PER_SECTION = 10
# --------------------


def clear_data():
    """Deletes all existing data from the models to start fresh."""
    print("🗑️ Deleting old data...")
    StudentResponse.objects.all().delete()
    Student.objects.all().delete()
    Option.objects.all().delete()
    Question.objects.all().delete()
    Section.objects.all().delete()
    Category.objects.all().delete()
    College.objects.all().delete()
    SubjectiveOption.objects.all().delete()
    SubjectiveOptionTemplate.objects.all().delete()
    print("✅ Old data deleted.")


def create_subjective_templates():
    """Creates reusable templates for subjective questions."""
    print("📝 Creating subjective option templates...")

    # Template 1: 5-Point Likert Scale
    likert_template, _ = SubjectiveOptionTemplate.objects.get_or_create(
        name='5-Point Likert Scale'
    )
    options_likert = [
        'Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'
    ]
    for option_text in options_likert:
        SubjectiveOption.objects.get_or_create(template=likert_template, text=option_text)

    # Template 2: Satisfaction Survey
    satisfaction_template, _ = SubjectiveOptionTemplate.objects.get_or_create(
        name='Satisfaction Survey'
    )
    options_satisfaction = [
        'Very Unsatisfied', 'Unsatisfied', 'Neutral', 'Satisfied', 'Very Satisfied'
    ]
    for option_text in options_satisfaction:
        SubjectiveOption.objects.get_or_create(template=satisfaction_template, text=option_text)
    
    print("✅ Subjective templates created.")
    return [likert_template, satisfaction_template]


def populate():
    """The main function to create all the data."""
    clear_data()
    subjective_templates = create_subjective_templates()

    # 1. Create Colleges
    print(f"🏫 Creating {NUM_COLLEGES} colleges...")
    colleges = []
    for _ in range(NUM_COLLEGES):
        college = College.objects.create(name=f"{fake.company()} University")
        colleges.append(college)
    print("✅ Colleges created.")

    all_questions = []

    # 2. Create Categories, Sections, and Questions for each College
    for college in colleges:
        print(f"\n--- Populating College: {college.name} ---")

        # Create one subjective category (e.g., for feedback)
        feedback_category = Category.objects.create(
            college=college,
            name='Campus Life Feedback',
            has_correct_answers=False
        )
        feedback_section = Section.objects.create(
            category=feedback_category,
            name='Student Satisfaction Survey',
            subjective_option_template=random.choice(subjective_templates)
        )
        for i in range(NUM_QUESTIONS_PER_SECTION):
            q_text = f"How satisfied are you with the {fake.random_element(elements=('library services', 'cafeteria food', 'sports facilities', 'hostel amenities', 'faculty support'))}?"
            # The Question.save() method will automatically create options for this
            question = Question.objects.create(section=feedback_section, text=q_text)
            all_questions.append(question)
        print(f"📊 Created subjective category '{feedback_category.name}' with {NUM_QUESTIONS_PER_SECTION} questions.")


        # Create one objective category (e.g., for a test)
        aptitude_category = Category.objects.create(
            college=college,
            name='General Aptitude Test',
            has_correct_answers=True
        )
        math_section = Section.objects.create(
            category=aptitude_category,
            name='Quantitative Analysis',
            # No subjective template needed here
        )
        for i in range(NUM_QUESTIONS_PER_SECTION):
            num1 = random.randint(10, 100)
            num2 = random.randint(10, 100)
            correct_answer = num1 + num2
            question = Question.objects.create(
                section=math_section,
                text=f"What is the sum of {num1} and {num2}?"
            )
            all_questions.append(question)
            
            # Since has_correct_answers=True, we must create options manually.
            options = [
                Option.objects.create(question=question, text=str(correct_answer), is_correct=True),
                Option.objects.create(question=question, text=str(correct_answer + random.randint(1, 5))),
                Option.objects.create(question=question, text=str(correct_answer - random.randint(1, 5))),
                Option.objects.create(question=question, text=str(random.randint(200, 300))),
            ]
            random.shuffle(options)
        print(f"✍️  Created objective category '{aptitude_category.name}' with {NUM_QUESTIONS_PER_SECTION} questions.")


        # 3. Create Students for this College
        print(f"🧑‍🎓 Creating {NUM_STUDENTS_PER_COLLEGE} students for {college.name}...")
        students_in_college = []
        for i in range(NUM_STUDENTS_PER_COLLEGE):
            student = Student.objects.create(
                college=college,
                student_id=f"S-{college.id}-{1000+i}",
                name=fake.name()
            )
            students_in_college.append(student)

        # 4. Create Student Responses
        print(f"📝 Simulating responses for students in {college.name}...")
        for student in students_in_college:
            # Each student answers a random number of questions (e.g., 5 to 15)
            questions_to_answer = random.sample(all_questions, k=random.randint(5, 15))
            for question in questions_to_answer:
                # Get the options for the current question
                possible_options = list(question.options.all())
                if possible_options:
                    # Choose a random option
                    selected = random.choice(possible_options)
                    StudentResponse.objects.create(
                        student=student,
                        question=question,
                        selected_option=selected
                    )
    
    print("\n\n🎉 --- Seeding Complete! --- 🎉")
    print(f"Total Colleges: {College.objects.count()}")
    print(f"Total Students: {Student.objects.count()}")
    print(f"Total Questions: {Question.objects.count()}")
    print(f"Total Responses: {StudentResponse.objects.count()}")


if __name__ == '__main__':
    populate()