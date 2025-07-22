from pydantic import BaseModel, validator
from typing import List, Optional
import datetime
from models import QuestionType # Import the enum


# --- Schemas for Options ---
class QuestionOptionBase(BaseModel):
    option_text: str

class QuestionOptionCreate(QuestionOptionBase):
    pass

class QuestionOption(QuestionOptionBase):
    id: int
    class Config:
        orm_mode = True

# --- Schemas for Questions (Updated) ---
class QuestionBase(BaseModel):
    question_text: str
    question_type: QuestionType
    is_mandatory: bool = False
    is_jd_specific: bool = False

class QuestionCreate(QuestionBase):
    # When creating a question, we can also pass its options
    options: Optional[List[QuestionOptionCreate]] = None

class Question(QuestionBase):
    id: int
    job_id: int
    options: List[QuestionOption] = [] # Always return options
    class Config:
        orm_mode = True

# --- Schemas for Responses (Updated) ---
class ResponseCreate(BaseModel):
    question_id: int
    # Candidate provides EITHER text OR a list of option IDs
    response_text: Optional[str] = None
    selected_option_ids: Optional[List[int]] = None

    # Validator to ensure one and only one type of answer is given
    @validator('selected_option_ids', always=True)
    def check_response_type(cls, v, values):
        if 'response_text' in values and values['response_text'] is not None and v is not None:
            raise ValueError('Provide either response_text or selected_option_ids, not both.')
        if ('response_text' not in values or values['response_text'] is None) and v is None:
            raise ValueError('Either response_text or selected_option_ids must be provided.')
        return v

class Response(BaseModel):
    id: int
    question_id: int
    response_text: Optional[str] = None
    submitted_at: datetime.datetime
    selected_options: List[QuestionOption] = [] # Return full option objects
    
    class Config:
        orm_mode = True
# Schemas for Questions
# class QuestionBase(BaseModel):
#     question_text: str
#     is_mandatory: bool = False
#     is_jd_specific: bool = False

# class QuestionCreate(QuestionBase):
#     pass

# class Question(QuestionBase):
#     id: int
#     job_id: int

#     class Config:
#         orm_mode = True

# Schemas for Jobs
class JobBase(BaseModel):
    title: str
    description: str

class JobCreate(JobBase):
    pass

class Job(JobBase):
    id: int
    created_at: datetime.datetime
    questions: List[Question] = []

    class Config:
        orm_mode = True

# Schemas for Candidates
class CandidateBase(BaseModel):
    first_name: str
    last_name: str
    email: str

class CandidateCreate(CandidateBase):
    pass

class Candidate(CandidateBase):
    id: int
    created_at: datetime.datetime

    class Config:
        orm_mode = True
        
# Schemas for Screening Sessions & Responses
# class ResponseCreate(BaseModel):
#     question_id: int
#     response_text: str

# class Response(BaseModel):
#     id: int
#     question_id: int
#     response_text: str
#     submitted_at: datetime.datetime
    
#     class Config:
#         orm_mode = True

class ScreeningSessionCreate(BaseModel):
    job_id: int
    candidate_ids: List[int]

class ScreeningSession(BaseModel):
    id: int
    job_id: int
    created_at: datetime.datetime
    
    class Config:
        orm_mode = True

class ScreeningSessionLink(BaseModel):
    candidate_id: int
    candidate_email: str
    access_token: str # The token to build the magic link, e.g., https://frontend.com/test/{access_token}

    class Config:
        orm_mode = True

# NEW: The detailed response for the employer after creating a session
class ScreeningSessionCreationResponse(BaseModel):
    session_id: int
    job_id: int
    candidate_links: List[ScreeningSessionLink]

# NEW: The payload the candidate's frontend receives to build the test page
class ScreeningTestPayload(BaseModel):
    job_title: str
    job_description: str
    candidate_id: int
    session_id: int
    questions: List[Question] # Use the existing detailed Question schema

    class Config:
        orm_mode = True

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    is_mandatory: Optional[bool] = None

class QuestionOptionUpdate(BaseModel):
    option_text: Optional[str] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class CandidateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

# --- NEW: Schemas for Viewing Screening Results ---

class AnswerResult(BaseModel):
    """Represents a single formatted answer."""
    question_text: str
    question_type: QuestionType
    response_text: Optional[str] = None
    selected_options: List[QuestionOption] = []

    class Config:
        orm_mode = True

class CandidateResult(BaseModel):
    """Represents the full submission from a single candidate."""
    candidate_id: int
    first_name: str
    last_name: str
    email: str
    responses: List[AnswerResult]

class ScreeningResults(BaseModel):
    """The top-level response model for the entire screening session report."""
    session_id: int
    job_id: int
    job_title: str
    results: List[CandidateResult]
