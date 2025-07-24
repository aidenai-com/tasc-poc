# schemas.py
import uuid
from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional
import datetime

# =======================================================================
#                            BASE & SHARED SCHEMAS
# =======================================================================
class QuestionOption(BaseModel):
    id: str
    option_text: str

# =======================================================================
#                           COMPANY SCHEMAS
# =======================================================================
class CompanyBase(BaseModel):
    name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                           CANDIDATE SUB-SCHEMAS
# =======================================================================
class Education(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class Experience(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
# (Add other sub-schemas like Skill, Language, etc. as needed)

# =======================================================================
#                           CANDIDATE SCHEMAS
# =======================================================================
class CandidateBase(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

class CandidateCreate(CandidateBase):
    full_name: str
    email: str

class CandidateUpdate(CandidateBase):
    pass

class Candidate(CandidateBase):
    id: uuid.UUID
    education: List[Education] = []
    experiences: List[Experience] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                            FORM BUILDER SCHEMAS
# =======================================================================
class QuestionBase(BaseModel):
    question_text: str
    question_type: str

class QuestionCreate(QuestionBase):
    pass

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    # order: Optional[int] = None

class Question(QuestionBase):
    id: uuid.UUID
    # We removed 'order' as requested
    options: List[QuestionOption] = []
    
    model_config = ConfigDict(from_attributes=True)

    # --- THIS IS THE NEW, CORRECTED LOGIC ---
    @field_validator('options', mode='before')
    @classmethod
    def transform_options_from_orm(cls, v, info):
        """
        This validator runs before Pydantic tries to validate the 'options' field.
        It checks if the input 'v' is a string (coming from the database model)
        and transforms it into the list of objects Pydantic expects.
        """
        if isinstance(v, str):
            # If v is a string like "Yes,No", split it
            opts_list = [o.strip() for o in v.split(',') if o.strip()]
            # Transform it into the required List[QuestionOption] format
            return [QuestionOption(id=opt, option_text=opt) for opt in opts_list]
        
        # If 'v' is already a list or None, let it pass through to the default validator
        return v

# class QuestionReorderRequest(BaseModel):
#     ordered_ids: List[uuid.UUID]

class QuestionSet(BaseModel):
    id: uuid.UUID
    name: str
    questions: List[Question] = []
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                               JOB SCHEMAS
# =======================================================================
class JobBase(BaseModel):
    title: str

class JobCreate(JobBase):
    company_id: uuid.UUID

class Job(JobBase):
    id: uuid.UUID
    question_sets: List[QuestionSet] = []
    model_config = ConfigDict(from_attributes=True)

# =======================================================================
#                           APPLICATION & SCREENING
# =======================================================================
class ApplicationBase(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str # Using str for simplicity, can use the Enum

class ApplicationCreate(ApplicationBase):
    pass

class Application(ApplicationBase):
    id: uuid.UUID
    applied_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class ScreeningTestSendRequest(BaseModel):
    application_ids: List[uuid.UUID]

class ScreeningTestLink(BaseModel):
    application_id: uuid.UUID
    test_link_id: uuid.UUID
    candidate_email: Optional[str] = None

class ScreeningTestSendResponse(BaseModel):
    links: List[ScreeningTestLink]

class TakeTestPayload(BaseModel):
    job_title: str
    response_session_id: uuid.UUID
    application_id: uuid.UUID
    questions: List[Question]

class ResponseCreate(BaseModel):
    question_id: uuid.UUID
    answer: Optional[str] = None

class Response(ResponseCreate):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)