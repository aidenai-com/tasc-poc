# main.py
import uuid
import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
import ollama
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import your project-specific modules
import models
import schemas
import database

app = FastAPI(title="TASC Production API")
origins = [
    "http://localhost:3000", # The origin for your React app
    "http://localhost:3001", # A common alternative port for React
    "http://localhost:5173", # The default for Vite, another popular tool
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Specifies the allowed origins
    allow_credentials=True,      # Allows cookies to be included in requests
    allow_methods=["*"],         # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],         # Allows all headers
)

# Ollama client setup
try:
    ollama_client = ollama.Client(host="http://localhost:11434/")
    ollama_client.list()
    print("Successfully connected to Ollama.")
except Exception as e:
    print(f"Could not connect to Ollama. AI features will fail. Error: {e}")
    ollama_client = None

# --- Helper Functions ---

async def get_job_by_id(job_id: int, db: AsyncSession):
    """Helper to fetch a job by its ID, raises 404 if not found."""
    result = await db.execute(select(models.Job).where(models.Job.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with ID {job_id} not found")
    return job

# =======================================================================
#                            EMPLOYER FLOW
# =======================================================================

@app.post("/companies/", response_model=schemas.Company, status_code=status.HTTP_201_CREATED, tags=["Employer Flow - Setup"])
async def create_company(company_data: schemas.CompanyCreate, db: AsyncSession = Depends(database.get_db)):
    """
    Creates a new Company. This is a prerequisite for creating a Job.
    """
    # Optional: Check if a company with the same name already exists
    existing_company = await db.execute(select(models.Company).where(models.Company.name == company_data.name))
    if existing_company.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A company with this name already exists.")
        
    db_company = models.Company(**company_data.model_dump())
    db.add(db_company)
    await db.commit()
    await db.refresh(db_company)
    return db_company

# --- Job and Automatic QuestionSet Creation ---
@app.post("/jobs/", response_model=schemas.Job, status_code=201, tags=["Employer Flow - Jobs"])
async def create_job(job_data: schemas.JobCreate, db: AsyncSession = Depends(database.get_db)):
    """
    Creates a new Job and automatically creates an empty 'Prescreening' QuestionSet for it.
    """
    # Step 1: Create objects in memory
    db_job = models.Job(**job_data.model_dump())
    prescreening_set = models.QuestionSet(name="Prescreening", job=db_job)
    db.add(db_job)
    db.add(prescreening_set)
    
    # Step 2: Flush to the database to get the ID assigned by the DB
    await db.flush()
    
    # --- THIS IS THE FIX ---
    # Safely store the new ID before the commit expires the object
    new_job_id = db_job.id
    
    # Step 3: Commit the transaction to save permanently
    await db.commit()
    
    # Step 4: Use the safe ID to perform a clean re-fetch
    query = (
        select(models.Job)
        .options(
            selectinload(models.Job.question_sets)
            .selectinload(models.QuestionSet.questions)
        )
        .where(models.Job.id == new_job_id)
    )
    result = await db.execute(query)
    final_job = result.scalars().unique().first()
    
    return final_job

# --- Candidate Management Endpoints (FIX: Added missing endpoints) ---
@app.post("/candidates/", response_model=schemas.Candidate, status_code=status.HTTP_201_CREATED, tags=["Employer Flow - Candidates"])
async def create_candidate(candidate_data: schemas.CandidateCreate, db: AsyncSession = Depends(database.get_db)):
    existing_candidate = await db.execute(select(models.Candidate).where(models.Candidate.email == candidate_data.email))
    if existing_candidate.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A candidate with this email already exists.")
        
    db_candidate = models.Candidate(**candidate_data.model_dump())
    db.add(db_candidate)
    await db.commit()
    await db.refresh(db_candidate)
    return db_candidate

@app.get("/candidates/", response_model=List[schemas.Candidate], tags=["Employer Flow - Candidates"])
async def list_candidates(db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(select(models.Candidate).order_by(models.Candidate.created_at.desc()))
    candidates = result.scalars().all()
    return candidates

@app.get("/candidates/{candidate_id}", response_model=schemas.Candidate, tags=["Employer Flow - Candidates"])
async def get_candidate(candidate_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = select(models.Candidate).options(selectinload(models.Candidate.education), selectinload(models.Candidate.experiences)).where(models.Candidate.id == candidate_id)
    result = await db.execute(query)
    candidate = result.scalars().unique().first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate

@app.patch("/candidates/{candidate_id}", response_model=schemas.Candidate, tags=["Employer Flow - Candidates"])
async def update_candidate(candidate_id: uuid.UUID, candidate_data: schemas.CandidateUpdate, db: AsyncSession = Depends(database.get_db)):
    db_candidate = await db.get(models.Candidate, candidate_id)
    if not db_candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    update_data = candidate_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_candidate, key, value)
    
    await db.commit()
    return await get_candidate(candidate_id, db)

@app.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow - Candidates"])
async def delete_candidate(candidate_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    db_candidate = await db.get(models.Candidate, candidate_id)
    if not db_candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    
    await db.delete(db_candidate)
    await db.commit()
    return

# --- Form Builder Endpoints ---
@app.get("/question-sets/{set_id}", response_model=schemas.QuestionSet, tags=["Employer Flow - Form Builder"])
async def get_question_set(set_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = select(models.QuestionSet).options(selectinload(models.QuestionSet.questions)).where(models.QuestionSet.id == set_id)
    result = await db.execute(query)
    q_set = result.scalars().unique().first()
    if not q_set:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "QuestionSet not found")
    return q_set

@app.post("/question-sets/{set_id}/questions", response_model=schemas.Question, status_code=201, tags=["Employer Flow - Form Builder"])
async def create_question(set_id: uuid.UUID, question_data: schemas.QuestionCreate, db: AsyncSession = Depends(database.get_db)):
    """
    Adds a new Yes/No question to a specific QuestionSet.
    Automatically sets options to "Yes,No".
    """
    # Force the question type to be mcq_single
    question_dict = question_data.model_dump()
    question_dict['question_type'] = 'mcq_single'

    db_question = models.Question(set_id=set_id, **question_dict)
    db_question.options = "Yes,No"
    
    db.add(db_question)
    await db.commit()
    await db.refresh(db_question)
    return db_question

@app.patch("/questions/{question_id}", response_model=schemas.Question, tags=["Employer Flow - Form Builder"])
async def update_question(question_id: uuid.UUID, question_update: schemas.QuestionUpdate, db: AsyncSession = Depends(database.get_db)):
    db_question = await db.get(models.Question, question_id)
    if not db_question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    update_data = question_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_question, key, value)
    await db.commit()
    await db.refresh(db_question)
    return db_question

@app.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow - Form Builder"])
async def delete_question(question_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    db_question = await db.get(models.Question, question_id)
    if not db_question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    await db.delete(db_question)
    await db.commit()
    return

@app.patch("/question-sets/{set_id}/reorder", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow - Form Builder"])
async def reorder_questions(set_id: uuid.UUID, request_data: schemas.QuestionReorderRequest, db: AsyncSession = Depends(database.get_db)):
    order_mapping = {question_id: index for index, question_id in enumerate(request_data.ordered_ids)}
    result = await db.execute(select(models.Question).where(models.Question.set_id == set_id))
    questions_in_set = result.scalars().all()
    for question in questions_in_set:
        if question.id in order_mapping:
            question.order = order_mapping[question.id]
    await db.commit()
    return

# --- Screening Flow Endpoints ---
@app.post("/send-screening-tests", response_model=schemas.ScreeningTestSendResponse, tags=["Employer Flow - Screening"])
async def send_screening_tests(request_data: schemas.ScreeningTestSendRequest, db: AsyncSession = Depends(database.get_db)):
    if not request_data.application_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No application IDs provided.")
    app_query = select(models.Application).options(selectinload(models.Application.candidate)).where(models.Application.id.in_(request_data.application_ids))
    applications = (await db.execute(app_query)).scalars().all()
    if len(applications) != len(set(request_data.application_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more applications not found.")
    job_id = applications[0].job_id
    qset_query = select(models.QuestionSet).where(models.QuestionSet.job_id == job_id, models.QuestionSet.name == "Prescreening")
    question_set = (await db.execute(qset_query)).scalars().first()
    if not question_set:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Prescreening question set not found for Job ID {job_id}")
    created_links = []
    for application in applications:
        db_session = models.ResponseSession(application_id=application.id, set_id=question_set.id)
        db.add(db_session)
        await db.flush()
        created_links.append(schemas.ScreeningTestLink(application_id=application.id, test_link_id=db_session.id, candidate_email=application.candidate.email if application.candidate else None))
    await db.commit()
    return schemas.ScreeningTestSendResponse(links=created_links)

# =======================================================================
#                            CANDIDATE FLOW
# =======================================================================
@app.get("/take-test/{session_id}", response_model=schemas.TakeTestPayload, tags=["Candidate Flow"])
async def get_test(session_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = select(models.ResponseSession).options(selectinload(models.ResponseSession.application).selectinload(models.Application.job), selectinload(models.ResponseSession.question_set).selectinload(models.QuestionSet.questions)).where(models.ResponseSession.id == session_id)
    result = await db.execute(query)
    session = result.scalars().unique().first()
    if not session or not session.application or not session.question_set:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test session not found or is incomplete.")
    return schemas.TakeTestPayload(job_title=session.application.job.title, response_session_id=session.id, application_id=session.application.id, questions=session.question_set.questions)

@app.post("/response-sessions/{session_id}/responses", response_model=schemas.Response, tags=["Candidate Flow"])
async def submit_response(session_id: uuid.UUID, response_data: schemas.ResponseCreate, db: AsyncSession = Depends(database.get_db)):
    db_response = models.Response(session_id=session_id, **response_data.model_dump())
    db.add(db_response)
    await db.flush()
    new_response_id = db_response.id
    await db.commit()
    final_response = await db.get(models.Response, new_response_id)
    return final_response

@app.post("/response-sessions/{session_id}/complete", tags=["Candidate Flow"])
async def complete_session(session_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = select(models.ResponseSession).options(selectinload(models.ResponseSession.application), selectinload(models.ResponseSession.question_set).selectinload(models.QuestionSet.questions), selectinload(models.ResponseSession.responses)).where(models.ResponseSession.id == session_id)
    session = (await db.execute(query)).scalars().unique().first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    all_passed = True
    for question in session.question_set.questions:
        response_for_question = next((r for r in session.responses if r.question_id == question.id), None)
        if not response_for_question or response_for_question.answer.lower() != 'yes':
            all_passed = False
            break
    if all_passed:
        session.application.status = models.ApplicationStatus.SCREENING_PASSED
    else:
        session.application.status = models.ApplicationStatus.SCREENING_FAILED
    session.completed_at = datetime.datetime.utcnow()
    await db.commit()
    return {"status": session.application.status.value}

if __name__ == "__main__":
    print("Starting Uvicorn server...")
    uvicorn.run(app="tasc_main:app", host="0.0.0.0", port=8080, reload=True)