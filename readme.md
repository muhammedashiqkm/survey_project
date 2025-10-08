
### 1\. Register Student

This endpoint registers a new student under a specific college.

  * **Endpoint URL**: `/register-student/`
  * **HTTP Method**: `POST`

#### Request Format

The request body must be a JSON object containing the student's ID, name, and the exact name of their college.

```json
{
    "student_id": "STU-00123",
    "name": "Arjun Kumar",
    "college_name": "Global Institute of Technology"
}
```

#### Success Response (`201 Created`)

Upon successful registration, the API returns a success message and the new student's internal database ID.

```json
{
    "message": "Student registered successfully",
    "student_id": 15
}
```

#### Error Response (`400 Bad Request`)

If the college name doesn't exist or a student with the same ID is already registered at that college, an error is returned.

```json
{
    "errors": {
        "college_name": ["College with name 'Invalid College' does not exist."]
    }
}
```

-----

### 2\. Get Survey Questions

This endpoint fetches the complete survey structure for a given college, including all categories, sections, questions, and options.

  * **Endpoint URL**: `/questions/<college_name>/`
  * **HTTP Method**: `GET`

#### Request Format

No request body is needed. The college's name should be included in the URL (e.g., `/questions/Global Institute of Technology/`).

#### Success Response (`200 OK`)

The response is a nested JSON object containing the entire survey for the specified college.

```json
{
    "college_name": "Global Institute of Technology",
    "categories": [
        {
            "name": "Aptitude Test",
            "has_correct_answers": true,
            "sections": [
                {
                    "name": "Quantitative",
                    "questions": [
                        {
                            "id": 1,
                            "text": "What is 10 + 25?",
                            "options": [
                                { "id": 1, "text": "30" },
                                { "id": 2, "text": "35" }
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "name": "Feedback Survey",
            "has_correct_answers": false,
            "sections": [
                {
                    "name": "Campus Facilities",
                    "questions": [
                        {
                            "id": 2,
                            "text": "How would you rate the library services?",
                            "options": [
                                { "id": 3, "text": "Excellent" },
                                { "id": 4, "text": "Good" }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}
```

#### Error Response (`404 Not Found`)

If no college with the specified name exists, a `404 Not Found` error is returned.

-----

### 3\. Submit Student Responses

This endpoint allows a student to submit their answers for multiple questions in a single request.

  * **Endpoint URL**: `/submit-answers/<college_name>/<student_id>/`
  * **HTTP Method**: `POST`

#### Request Format

The request body must contain a list of `responses`, where each object specifies a `question_id` and the `selected_option_id`.

```json
{
    "responses": [
        {
            "question_id": 1,
            "selected_option_id": 2
        },
        {
            "question_id": 2,
            "selected_option_id": 3
        }
    ]
}
```

#### Success Response (`201 Created`)

On successful submission, the API returns a confirmation message.

```json
{
    "message": "Responses submitted successfully"
}
```

#### Error Response (`400 Bad Request` / `404 Not Found`)

An error is returned if the request data is invalid, question/option IDs don't exist, or the student/college is not found.

```json
{
    "error": "Invalid question_id or selected_option_id referenced",
    "missing_questions": [999],
    "missing_options": []
}
```

-----

### 4\. Get Student Results

This endpoint retrieves the processed results for a student, separated into objective (marks-based) and subjective (text-based) categories.

  * **Endpoint URL**: `/students/<college_name>/<student_id>/results/`
  * **HTTP Method**: `GET`

#### Request Format

No request body is needed. The `college_name` and `student_id` are specified in the URL.

#### Success Response (`200 OK`)

The API returns a detailed breakdown of the student's results, grouped by category.

```json
{
    "student_name": "Arjun Kumar",
    "student_id": "STU-00123",
    "results": [
        {
            "category": "Aptitude Test",
            "sections": [
                {
                    "section": "Quantitative",
                    "result_type": "marks",
                    "score": 15
                }
            ]
        },
        {
            "category": "Feedback Survey",
            "sections": [
                {
                    "section": "Campus Facilities",
                    "result_type": "subjective",
                    "responses": [
                        {
                            "question": "How would you rate the library services?",
                            "selected_option": "Excellent"
                        }
                    ]
                }
            ]
        }
    ]
}
```

#### Error Response (`404 Not Found`)

A `404 Not Found` error is returned if the specified college or student ID does not exist.