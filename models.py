from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Boolean, Float, Date, Enum, JSON, UniqueConstraint, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()
UUIDCol = PG_UUID(as_uuid=True)

# Enums
class JobStatus(enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    FILLED = "FILLED"

class ApplicationStatus(enum.Enum):
    SOURCED = "SOURCED"
    SCREENING_PASSED = "SCREENING_PASSED"
    SCREENING_FAILED = "SCREENING_FAILED"
    RANKED = "RANKED"
    REJECTED = "REJECTED"

class EmploymentType(enum.Enum):
    full_time = "Full-time"
    part_time = "Part-time"
    contract = "Contract"
    internship = "Internship"
    freelance = "Freelance"

class DocumentType(enum.Enum):
    resume = "Resume"
    cover_letter = "Cover Letter"
    id_proof = "ID Proof"

class EntryType(enum.Enum):
    project = "Project"
    award = "Award"
    achievement = "Achievement"
    leadership = "Leadership"

class SkillCategory(enum.Enum):
    technical = "Technical"
    soft_skill = "Soft Skill"
    language = "Language"
    tool = "Tool"
    professional = "Professional"

class InterviewStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class InterviewResult(enum.Enum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"

# Tables

class Insights(Base):
    __tablename__ = 'insights'

    id = Column(Integer, primary_key=True, nullable=False)
    company_name = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    is_b2b = Column(Boolean, nullable=True)
    founded_year = Column(Integer, nullable=True)
    size_range = Column(Text, nullable=True)
    employees_count = Column(Integer, nullable=True)
    followers_count_linkedin = Column(Integer, nullable=True)
    linkedin_url = Column(Text, nullable=True)
    website = Column(Text, nullable=True)
    hq_country = Column(Text, nullable=True)
    hq_city = Column(Text, nullable=True)
    active_job_postings_count = Column(Integer, nullable=True)
    employees_count_by_month = Column(JSON, nullable=False, default=[])
    active_job_postings = Column(JSON, nullable=False, default=[])
    total_salary = Column(JSON, nullable=False, default=[])
    revenue_annual = Column(JSON, nullable=False, default={})
    employees_count_change = Column(JSON, nullable=False, default={})
    active_job_postings_count_change = Column(JSON, nullable=False, default={}) 
    active_job_postings_count_by_month = Column(JSON, nullable=False, default=[]) 





class Company(Base):
    __tablename__ = 'companies'
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    industry = Column(String)
    description = Column(Text)
    website = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    company_id = Column(UUIDCol, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    department = Column(String(120))
    domain = Column(String(120))
    location = Column(String(120))
    status = Column(Enum(JobStatus), default=JobStatus.DRAFT)
    employment_type = Column(Enum(EmploymentType))
    min_experience = Column(Float)
    salary_range = Column(String(120))
    must_have_skills = Column(JSON, default=list)
    extra_criteria = Column(Text)
    company_summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    company = relationship("Company", back_populates="jobs")
    job_description = relationship("JobDescription", uselist=False, back_populates="job", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    question_sets = relationship("QuestionSet", back_populates="job", cascade="all, delete-orphan")

class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUIDCol, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_summary = Column(Text)
    full_description = Column(Text)
    parsed_skills_json = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    job = relationship("Job", back_populates="job_description")

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    full_name = Column(String)
    email = Column(String)
    phone = Column(String)
    dob = Column(Date)
    gender = Column(String)
    nationality = Column(String)
    religion = Column(String)
    marital_status = Column(String)
    location = Column(String)
    address = Column(Text)
    linkedin_url = Column(String)
    website_url = Column(String)
    about_me = Column(Text)
    visa_status = Column(String)
    passport_number = Column(String)
    driving_license = Column(String)
    domain = Column(ARRAY(String))
    functional_area = Column(ARRAY(String))
    industry = Column(ARRAY(String))
    total_experience_years = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    applications = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="candidate", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="candidate", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="candidate", cascade="all, delete-orphan")
    languages = relationship("Language", back_populates="candidate", cascade="all, delete-orphan")
    certifications = relationship("Certification", back_populates="candidate", cascade="all, delete-orphan")
    projects = relationship("ProjectAchievement", back_populates="candidate", cascade="all, delete-orphan")
    interests = relationship("Interest", back_populates="candidate", cascade="all, delete-orphan")
    preferences = relationship("EmploymentPreference", uselist=False, back_populates="candidate", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="candidate", cascade="all, delete-orphan")

class Application(Base):
    __tablename__ = "applications"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUIDCol, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(ApplicationStatus), nullable=False)
    screening_notes = Column(Text)
    fitment_score = Column(Float)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    response_sessions = relationship("ResponseSession", back_populates="application", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="_job_candidate_uc"),)

class QuestionSet(Base):
    __tablename__ = "question_sets"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUIDCol, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    job = relationship("Job", back_populates="question_sets")
    questions = relationship("Question", back_populates="question_set", cascade="all, delete-orphan")
    response_sessions = relationship("ResponseSession", back_populates="question_set")

class Question(Base):
    __tablename__ = "questions"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    set_id = Column(UUIDCol, ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(Text)
    question_type = Column(String(50), nullable=False)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    question_set = relationship("QuestionSet", back_populates="questions")
    responses = relationship("Response", back_populates="question", cascade="all, delete-orphan")

class ResponseSession(Base):
    __tablename__ = "response_sessions"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    application_id = Column(UUIDCol, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    set_id = Column(UUIDCol, ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(InterviewStatus), default=InterviewStatus.PENDING, nullable=False)
    overall_summary = Column(Text)
    score = Column(Float(precision=2))
    skill_gaps = Column(JSON)
    result = Column(Enum(InterviewResult))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    question_set = relationship("QuestionSet", back_populates="response_sessions")
    application = relationship("Application", back_populates="response_sessions")
    responses = relationship("Response", back_populates="session", cascade="all, delete-orphan")

class Response(Base):
    __tablename__ = "responses"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    session_id = Column(UUIDCol, ForeignKey("response_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUIDCol, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    session = relationship("ResponseSession", back_populates="responses")
    question = relationship("Question", back_populates="responses")
    
    
class Education(Base):
    __tablename__ = "educations"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    degree = Column(String)
    field_of_study = Column(String)
    majors = Column(ARRAY(String))
    institution = Column(String)
    location = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    notes = Column(Text)
    raw_text = Column(Text)

    candidate = relationship("Candidate", back_populates="education")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Experience(Base):
    __tablename__ = "experiences"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    title = Column(String)
    company_name = Column(String)
    location = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    description = Column(Text)
    achievements = Column(ARRAY(Text))
    raw_text = Column(Text)

    candidate = relationship("Candidate", back_populates="experiences")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Skill(Base):
    __tablename__ = "skills"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    skill_name = Column(String)
    category = Column(String)
    proficiency = Column(String)
    months_experience = Column(Integer)
    last_used = Column(Date)

    candidate = relationship("Candidate", back_populates="skills")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Language(Base):
    __tablename__ = "languages"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    language = Column(String)
    proficiency = Column(String)
    read = Column(Boolean)
    write = Column(Boolean)
    speak = Column(Boolean)

    candidate = relationship("Candidate", back_populates="languages")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Certification(Base):
    __tablename__ = "certifications"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    title = Column(String)
    issuer = Column(String)
    issue_date = Column(Date)
    expiry_date = Column(Date)
    description = Column(Text)

    candidate = relationship("Candidate", back_populates="certifications")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProjectAchievement(Base):
    __tablename__ = "project_achievements"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    type = Column(String)
    title = Column(String)
    description = Column(Text)
    date = Column(Date)

    candidate = relationship("Candidate", back_populates="projects")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Interest(Base):
    __tablename__ = "interests"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    interest = Column(String)

    candidate = relationship("Candidate", back_populates="interests")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmploymentPreference(Base):
    __tablename__ = "employment_preferences"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    preferred_location = Column(ARRAY(String))
    willing_to_relocate = Column(Boolean)
    employment_type = Column(String)
    notice_period_days = Column(Integer)

    candidate = relationship("Candidate", back_populates="preferences")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUIDCol, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUIDCol, ForeignKey("candidates.id", ondelete="CASCADE"))
    type = Column(String)
    file_path = Column(String)
    uploaded_at = Column(DateTime)

    # Optional parsing metadata
    document_language = Column(String)
    document_culture = Column(String)
    parser_settings = Column(Text)
    extracted_sections = Column(JSON)

    candidate = relationship("Candidate", back_populates="documents")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())