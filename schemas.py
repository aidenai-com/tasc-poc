# schemas.py
from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional
import datetime

# Import the enum from your models to ensure consistency
from models import QuestionType

# =======================================================================
#                            OPTION SCHEMAS
# =======================================================================
class QuestionOptionBase(BaseModel):
    option_text: str

class QuestionOptionCreate(QuestionOptionBase):
    pass

class QuestionOptionUpdate(QuestionOptionBase):
    pass

class QuestionReorderRequest(BaseModel):
    ordered_ids: List[int]

class QuestionOption(QuestionOptionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                           QUESTION SCHEMAS
# =======================================================================
class QuestionBase(BaseModel):
    question_text: str
    question_type: QuestionType
    is_mandatory: bool = False
    is_jd_specific: bool = False

class QuestionCreate(QuestionBase):
    # Allows creating a question with its options in a single API call
    options: Optional[List[QuestionOptionCreate]] = None

class QuestionUpdate(BaseModel):
    # All fields are optional for PATCH requests
    question_text: Optional[str] = None
    is_mandatory: Optional[bool] = None

class Question(QuestionBase):
    id: int
    job_id: int
    order: int  # Ensure the 'order' field is included in the response
    options: List[QuestionOption] = []
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                               JOB SCHEMAS
# =======================================================================
class JobBase(BaseModel):
    title: str
    description: Optional[str] = None

class JobCreate(JobBase):
    pass

class JobUpdate(JobBase):
    title: Optional[str] = None
    description: Optional[str] = None

class Job(JobBase):
    id: int
    created_at: datetime.datetime
    questions: List[Question] = []
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                           CANDIDATE SCHEMAS
# =======================================================================
class CandidateBase(BaseModel):
    first_name: str
    last_name: str
    email: str

class CandidateCreate(CandidateBase):
    pass

class CandidateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None

class Candidate(CandidateBase):
    id: int
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                           RESPONSE SCHEMAS
# =======================================================================
class ResponseCreate(BaseModel):
    question_id: int
    session_id: int # Include session_id for submission
    candidate_id: int # Include candidate_id for submission
    response_text: Optional[str] = None
    selected_option_ids: Optional[List[int]] = None

    # Validator to ensure one and only one type of answer is given
    @field_validator('selected_option_ids', mode='after')
    @classmethod
    def check_response_type(cls, v, info):
        values = info.data
        if 'response_text' in values and values.get('response_text') is not None and v is not None:
            raise ValueError('Provide either response_text or selected_option_ids, not both.')
        if ('response_text' not in values or values.get('response_text') is None) and (v is None or not v):
            raise ValueError('Either response_text or selected_option_ids must be provided.')
        return v

class Response(BaseModel):
    id: int
    question_id: int
    response_text: Optional[str] = None
    submitted_at: datetime.datetime
    selected_options: List[QuestionOption] = []
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                      SCREENING SESSION SCHEMAS
# =======================================================================

class ScreeningSession(BaseModel):
    id: int
    job_id: int
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class ScreeningSessionCreate(BaseModel):
    job_id: int
    candidate_ids: List[int]

class ScreeningSessionLink(BaseModel):
    candidate_id: int
    candidate_email: str
    access_token: str

class ScreeningSessionCreationResponse(BaseModel):
    session_id: int
    job_id: int
    candidate_links: List[ScreeningSessionLink]

class ScreeningTestPayload(BaseModel):
    job_title: str
    job_description: Optional[str] # Description can be optional
    candidate_id: int
    session_id: int
    questions: List[Question]
    # No config needed here as it's not built directly from a single DB model

# --- Schemas for Viewing Screening Results ---
class AnswerResult(BaseModel):
    """Represents a single formatted answer for the results view."""
    question_text: str
    question_type: QuestionType
    response_text: Optional[str] = None
    selected_options: List[QuestionOption] = []
    model_config = ConfigDict(from_attributes=True)

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