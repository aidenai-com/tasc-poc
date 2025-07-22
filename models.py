import datetime
import enum  # Import the enum module
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,  # Import Enum type
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid  # Import uuid for unique identifiers

Base = declarative_base()

class QuestionType(enum.Enum):
    TEXT = "text"
    MCQ_SINGLE = "mcq_single" # Radio button style
    MCQ_MULTIPLE = "mcq_multiple" # Checkbox style

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    questions = relationship("Question", back_populates="job", order_by="Question.order")
    screening_sessions = relationship("ScreeningSession", back_populates="job")

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    responses = relationship("Response", back_populates="candidate")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    question_text = Column(Text, nullable=False)
    
    question_type = Column(Enum(QuestionType), nullable=False, default=QuestionType.TEXT)

    order = Column(Integer, nullable=False, default=0) 
    
    is_mandatory = Column(Boolean, default=False)
    is_jd_specific = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    job = relationship("Job", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="question")


class QuestionOption(Base):
    __tablename__ = "question_options"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    option_text = Column(Text, nullable=False)
    
    question = relationship("Question", back_populates="options")

class ScreeningSession(Base):
    __tablename__ = "screening_sessions"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    job = relationship("Job", back_populates="screening_sessions")
    responses = relationship("Response", back_populates="session")
    session_candidates = relationship("SessionCandidate", back_populates="session")


class SessionCandidate(Base):
    __tablename__ = "session_candidates"
    session_id = Column(Integer, ForeignKey("screening_sessions.id"), primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), primary_key=True)
    
    # NEW: The unique token for the candidate to access this specific session.
    # This will be our "magic link" identifier.
    access_token = Column(String, default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True)

    # NEW: Relationships to easily navigate from the association object
    session = relationship("ScreeningSession", back_populates="session_candidates")
    candidate = relationship("Candidate")


class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("screening_sessions.id"))
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    
    response_text = Column(Text, nullable=True) 
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    session = relationship("ScreeningSession", back_populates="responses")
    candidate = relationship("Candidate", back_populates="responses")
    question = relationship("Question", back_populates="responses")
    
    selected_options = relationship("QuestionOption", secondary="response_options")

class ResponseOption(Base):
    __tablename__ = "response_options"
    response_id = Column(Integer, ForeignKey("responses.id"), primary_key=True)
    option_id = Column(Integer, ForeignKey("question_options.id"), primary_key=True)