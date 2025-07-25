# schemas.py
import uuid
from pydantic import BaseModel, ConfigDict, field_validator, computed_field
from typing import List, Optional
import datetime
from models_final import InterviewStatus, InterviewResult # Import Enums

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

# =======================================================================
#                           CANDIDATE SCHEMAS
# =======================================================================
class CandidateBase(BaseModel):
    id: uuid.UUID # Added ID for consistency
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CandidateCreate(BaseModel): # Simplified for creation
    full_name: str
    email: str

class CandidateUpdate(CandidateBase):
    pass

class Candidate(CandidateBase):
    education: List[Education] = []
    experiences: List[Experience] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime

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

class Question(QuestionBase):
    id: uuid.UUID
    options: List[QuestionOption] = []
    model_config = ConfigDict(from_attributes=True)

    @field_validator('options', mode='before')
    @classmethod
    def transform_options_from_orm(cls, v, info):
        if isinstance(v, str):
            opts_list = [o.strip() for o in v.split(',') if o.strip()]
            return [QuestionOption(id=opt, option_text=opt) for opt in opts_list]
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
class _ApplicationForSession(BaseModel):
    job_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)

class ScreeningSession(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    created_at: datetime.datetime
    status: InterviewStatus # Use the Enum for type safety
    application: _ApplicationForSession
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def job_id(self) -> uuid.UUID:
        return self.application.job_id

class ApplicationBase(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str

class ApplicationCreate(ApplicationBase):
    pass

class Application(ApplicationBase):
    id: uuid.UUID
    applied_at: datetime.datetime
    updated_at: datetime.datetime
    candidate: CandidateBase # Include basic candidate info
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

class ScreeningSentResponse(BaseModel):
    message: str
    sent_count: int
    session_ids: List[uuid.UUID]

# =======================================================================
#        NEW RESPONSE SESSION SCHEMA for RESULTS
# =======================================================================
# This schema represents an Application with its nested Candidate.
# It's used within the main ResponseSession schema below.
class ApplicationWithCandidate(ApplicationBase):
    id: uuid.UUID
    candidate: CandidateBase # Nest the candidate schema
    model_config = ConfigDict(from_attributes=True)

# This is the new, comprehensive schema that was missing.
# It defines the structure for the /response-sessions/{session_id} endpoint.
class ResponseSession(BaseModel):
    id: uuid.UUID
    status: InterviewStatus
    result: Optional[InterviewResult] = None
    completed_at: Optional[datetime.datetime] = None
    
    # Nested relationships loaded from the database
    application: ApplicationWithCandidate
    question_set: QuestionSet
    responses: List[Response]
    
    model_config = ConfigDict(from_attributes=True)