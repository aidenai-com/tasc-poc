# tasc_main.py
import uuid
import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from typing import List
import ollama
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import your project-specific modules
import models
import schemas
import database


DEFAULT_PRESET_QUESTIONS = [
    "Will you now or in the future require sponsorship for employment visa status?(Yes/No)",
    "Have you completed the following level of education: Bachelor's Degree?(Yes/No)",
    "Do you have UAE Experience?",
    "we are looking only for Immediate Joiners. Are you currently unemployed ?",
    "Are you ok to work on a 3 month contract?(Yes/No)",
]


BANK_PRESET_QUESTIONS = [
    {"question_text": "Do you have experience in Emiratization Hiring?", "question_type": "mcq_single"},
    {"question_text": "How many years of work experience do you have with Contract Recruitment?", "question_type": "mcq_single"},
    {"question_text": "How many years of work experience do you have with 360 Recruitment?", "question_type": "mcq_single"},
    {"question_text": "How many years of work experience do you have with Insurance Claims?", "question_type": "mcq_single"},
    {"question_text": "How many years of work experience do you have with Microsoft Office?", "question_type": "mcq_single"},
    {"question_text": "Are you Native Arabic/Urdu Speaker?", "question_type": "mcq_single"},
    {"question_text": "This is 6 days working-Monday to Friday(full day) Saturday (half day) will you be interested?", "question_type": "mcq_single"},
    {"question_text": "Offered salary is 3000-4000 AED+ Transportation (No Accommodation provided) will u be interested?", "question_type": "mcq_single"},
]


app = FastAPI(title="TASC Production API")
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ollama client setup (remains the same)
try:
    ollama_client = ollama.Client(host="http://localhost:11434/")
    ollama_client.list()
    print("Successfully connected to Ollama.")
except Exception as e:
    print(f"Could not connect to Ollama. AI features will fail. Error: {e}")
    ollama_client = None

# =======================================================================
#                           COMPANY & CANDIDATE SETUP
# =======================================================================

@app.post("/companies/", response_model=schemas.Company, status_code=status.HTTP_201_CREATED, tags=["Setup"])
async def create_company(company_data: schemas.CompanyCreate, db: AsyncSession = Depends(database.get_db)):
    existing_company = await db.execute(select(models.Company).where(models.Company.name == company_data.name))
    if existing_company.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A company with this name already exists.")
    db_company = models.Company(**company_data.model_dump())
    db.add(db_company)
    await db.commit()
    await db.refresh(db_company)
    return db_company

@app.post("/candidates/", response_model=schemas.Candidate, status_code=status.HTTP_201_CREATED, tags=["Setup"])
async def create_candidate(candidate_data: schemas.CandidateCreate, db: AsyncSession = Depends(database.get_db)):
    existing_candidate = await db.execute(select(models.Candidate).where(models.Candidate.email == candidate_data.email))
    if existing_candidate.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A candidate with this email already exists.")
    db_candidate = models.Candidate(**candidate_data.model_dump())
    db.add(db_candidate)
    await db.commit()
    await db.refresh(db_candidate)
    return db_candidate

@app.post("/applications/", response_model=schemas.Application, status_code=status.HTTP_201_CREATED, tags=["Setup"])
async def create_application(app_data: schemas.ApplicationCreate, db: AsyncSession = Depends(database.get_db)):
    existing_app = await db.execute(select(models.Application).where(models.Application.job_id == app_data.job_id, models.Application.candidate_id == app_data.candidate_id))
    if existing_app.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This candidate has already been added to this job.")
    db_application = models.Application(**app_data.model_dump())
    db.add(db_application)
    
    await db.commit()
    await db.refresh(db_application)
    return db_application

# =======================================================================
#                            EMPLOYER FLOW - JOBS & FORMS
# =======================================================================

@app.get("/jobs", response_model=List[schemas.Job], tags=["Employer Flow - Jobs"])
async def list_jobs(db: AsyncSession = Depends(database.get_db)):
    """
    NEW: Retrieves a list of all jobs.
    """
    result = await db.execute(
        select(models.Job)
        .options(
            selectinload(models.Job.question_sets)
            .selectinload(models.QuestionSet.questions)
        )
        .order_by(models.Job.created_at.desc())
    )
    return result.unique().scalars().all()

@app.get("/jobs/{job_id}", response_model=schemas.Job, tags=["Employer Flow - Jobs"])
async def get_job_with_form(job_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    """
    MODIFIED: Retrieves a specific job and eagerly loads its question sets and questions.
    This is the main data source for the form builder page.
    """
    query = (
        select(models.Job)
        .options(
            selectinload(models.Job.question_sets)
            .selectinload(models.QuestionSet.questions)
        )
        .where(models.Job.id == job_id)
    )
    result = await db.execute(query)
    job = result.scalars().unique().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    for q_set in job.question_sets:
        for question in q_set.questions:
            if question.options is None:
                question.options = ''
    return job


@app.post("/jobs/", response_model=schemas.Job, status_code=201, tags=["Employer Flow - Jobs"])
async def create_job(job_data: schemas.JobCreate, db: AsyncSession = Depends(database.get_db)):
    """
    Creates a new Job and automatically creates a 'Prescreening' QuestionSet
    pre-populated with 5 default questions.
    """
    db_job = models.Job(**job_data.model_dump())
    prescreening_set = models.QuestionSet(name="Prescreening", job=db_job)
    
    db.add(db_job)
    db.add(prescreening_set)
    
    await db.flush()

    for q_text in DEFAULT_PRESET_QUESTIONS:
        new_question = models.Question(
            set_id=prescreening_set.id,
            question_text=q_text,
            question_type='mcq_single',
            options='Yes,No'
        )
        db.add(new_question)

    new_job_id = db_job.id
    
    await db.commit()

    return await get_job_with_form(job_id=new_job_id, db=db)

@app.post("/question-sets/{set_id}/questions", response_model=schemas.Question, status_code=201, tags=["Employer Flow - Form Builder"])
async def create_question(set_id: uuid.UUID, question_data: schemas.QuestionCreate, db: AsyncSession = Depends(database.get_db)):
    """
    MODIFIED: Adds a new question to a specific QuestionSet.
    Handles different question types and sets default options for 'Yes/No'.
    """
    q_set = await db.get(models.QuestionSet, set_id)
    if not q_set:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "QuestionSet not found")

    db_question = models.Question(set_id=set_id, **question_data.model_dump())
    
    # Specific logic for a 'yes_no' type if you add it, otherwise generic
    if db_question.question_type == 'mcq_single':
        db_question.options = "Yes,No"

    db.add(db_question)
    await db.commit()
    await db.refresh(db_question)

    if db_question.options is None:
        db_question.options = ''

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

# NOTE: The Question model needs an 'order' column for this to work.
# Add `order = Column(Integer, default=0)` to the `Question` model in `models.py`.
# @app.patch("/question-sets/{set_id}/reorder", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow - Form Builder"])
# async def reorder_questions(set_id: uuid.UUID, request_data: schemas.QuestionReorderRequest, db: AsyncSession = Depends(database.get_db)):
#     # This is a simplified implementation. A more robust one would use bulk updates.
#     for index, question_id in enumerate(request_data.ordered_ids):
#         question = await db.get(models.Question, question_id)
#         if question and question.set_id == set_id:
#             question.order = index
#     await db.commit()
#     return

# =======================================================================
#                            EMPLOYER FLOW - SCREENING
# =======================================================================
@app.get("/jobs/{job_id}/sessions", response_model=List[schemas.ScreeningSession], tags=["Employer Flow - Screening"])
async def get_sessions_for_job(job_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = (
        select(models.ResponseSession)
        .join(models.Application)
        .options(selectinload(models.ResponseSession.application))
        .where(models.Application.job_id == job_id)
        .order_by(models.ResponseSession.created_at.desc())
    )
    result = await db.execute(query)
    sessions = result.scalars().all()
    return sessions

@app.post("/send-screening-tests", response_model=schemas.ScreeningTestSendResponse, tags=["Employer Flow - Screening"])
async def send_screening_tests(request_data: schemas.ScreeningTestSendRequest, db: AsyncSession = Depends(database.get_db)):
    if not request_data.application_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No application IDs provided.")
        
    # Eager load related data
    app_query = (
        select(models.Application)
        .options(
            selectinload(models.Application.candidate),
            selectinload(models.Application.job).selectinload(models.Job.question_sets)
        )
        .where(models.Application.id.in_(request_data.application_ids))
    )
    applications = (await db.execute(app_query)).scalars().unique().all()

    if len(applications) != len(set(request_data.application_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more applications not found.")
        
    created_links = []
    for application in applications:
        # Find the "Prescreening" question set for the job
        prescreening_set = next((qs for qs in application.job.question_sets if qs.name == "Prescreening"), None)
        if not prescreening_set:
            # Skip this application if the job doesn't have the required set
            continue
        
        db_session = models.ResponseSession(application_id=application.id, set_id=prescreening_set.id)
        db.add(db_session)
        await db.flush() # Flush to get the ID
        created_links.append(schemas.ScreeningTestLink(
            application_id=application.id, 
            test_link_id=db_session.id, 
            candidate_email=application.candidate.email if application.candidate else None
        ))
        
    await db.commit()
    return schemas.ScreeningTestSendResponse(links=created_links)

@app.post("/jobs/{job_id}/send-to-sourced", response_model=schemas.ScreeningSentResponse, tags=["Employer Flow - Screening"])
async def send_to_all_sourced_candidates(job_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    """
    Finds all 'SOURCED' applications for a given job and creates a ResponseSession for each.
    The Application status remains 'SOURCED'.
    """
    # ... (Steps 1, 2, and 3 for finding applications and the question set are the same)
    app_query = (
        select(models.Application.id)
        .where(
            models.Application.job_id == job_id,
            models.Application.status == models.ApplicationStatus.SOURCED
        )
    )
    application_ids = (await db.execute(app_query)).scalars().all()

    if not application_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No 'SOURCED' candidates found for this job to send tests to."
        )

    # We only need the application IDs and the question set ID for this operation.
    # This simplifies the query significantly.
    qset_query = select(models.QuestionSet.id).where(
        models.QuestionSet.job_id == job_id,
        models.QuestionSet.name == "Prescreening"
    )
    question_set_id = (await db.execute(qset_query)).scalar_one_or_none()

    if not question_set_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prescreening question set not found for Job ID {job_id}. Cannot send tests."
        )

    # Step 4: Create a ResponseSession for each application.
    created_session_ids = []
    for app_id in application_ids:
        # Create the test session. Its default status is 'PENDING'.
        db_session = models.ResponseSession(application_id=app_id, set_id=question_set_id)
        db.add(db_session)
        
        # --- THIS IS THE FIX ---
        # We no longer change the application.status here. It stays as SOURCED.
        
        await db.flush()
        created_session_ids.append(db_session.id)

    await db.commit()

    return schemas.ScreeningSentResponse(
        message=f"Successfully initiated screening for {len(created_session_ids)} sourced candidates.",
        sent_count=len(created_session_ids),
        session_ids=created_session_ids
    )

# =======================================================================
#                            CANDIDATE FLOW
# =======================================================================
@app.get("/take-test/{session_id}", response_model=schemas.TakeTestPayload, tags=["Candidate Flow"])
async def get_test(session_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = (
        select(models.ResponseSession)
        .options(
            selectinload(models.ResponseSession.application).selectinload(models.Application.job), 
            selectinload(models.ResponseSession.question_set).selectinload(models.QuestionSet.questions)
        )
        .where(models.ResponseSession.id == session_id)
    )
    result = await db.execute(query)
    session = result.scalars().unique().first()
    
    if not session or not session.application or not session.question_set:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test session not found or is incomplete.")
        
    if session.status == models.InterviewStatus.PENDING:
        session.status = models.InterviewStatus.IN_PROGRESS
        await db.commit()
        await db.refresh(session)
        
    return schemas.TakeTestPayload(
        job_title=session.application.job.title,
        response_session_id=session.id,
        application_id=session.application.id,
        questions=session.question_set.questions
    )

@app.post("/response-sessions/{session_id}/responses", response_model=schemas.Response, tags=["Candidate Flow"])
async def submit_response(session_id: uuid.UUID, response_data: schemas.ResponseCreate, db: AsyncSession = Depends(database.get_db)):
    # Check if session exists
    session = await db.get(models.ResponseSession, session_id)
    if not session:
         raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    
    db_response = models.Response(session_id=session_id, **response_data.model_dump())
    db.add(db_response)
    await db.commit()
    await db.refresh(db_response)
    return db_response

@app.post("/response-sessions/{session_id}/complete", tags=["Candidate Flow"])
async def complete_session(session_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    query = (
        select(models.ResponseSession)
        .options(
            selectinload(models.ResponseSession.application),
            selectinload(models.ResponseSession.question_set).selectinload(models.QuestionSet.questions),
            selectinload(models.ResponseSession.responses)
        )
        .where(models.ResponseSession.id == session_id)
    )
    session = (await db.execute(query)).scalars().unique().first()

    if not session or not session.application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session or related Application not found")
    
    all_passed = True
    # Only evaluate "Yes/No" questions for this simple logic
    yes_no_questions = [
        q for q in session.question_set.questions 
        if q.question_type == 'mcq_single' and q.options and all(opt in q.options for opt in ['Yes', 'No'])
    ]
    
    for question in yes_no_questions:
        response_for_question = next((r for r in session.responses if r.question_id == question.id), None)
        if not response_for_question or response_for_question.answer.lower() != 'yes':
            all_passed = False
            break

    new_status = models.ApplicationStatus.SCREENING_PASSED if all_passed else models.ApplicationStatus.SCREENING_FAILED
        
    session.application.status = new_status
    session.status = models.InterviewStatus.COMPLETED
    session.result = models.InterviewResult.SELECTED if all_passed else models.InterviewResult.REJECTED
    session.completed_at = datetime.datetime.now(datetime.timezone.utc)
    
    await db.commit()
    
    return {"status": new_status.value}

@app.get("/response-sessions/{session_id}", response_model=schemas.ResponseSession, tags=["Employer Flow - Results"])
async def get_session_results(session_id: uuid.UUID, db: AsyncSession = Depends(database.get_db)):
    """
    NEW: Retrieves a complete session with its application, questions, and responses.
    This is used by the new ResultsPage.
    """
    query = (
        select(models.ResponseSession)
        .options(
            selectinload(models.ResponseSession.application).selectinload(models.Application.candidate),
            selectinload(models.ResponseSession.question_set).selectinload(models.QuestionSet.questions),
            selectinload(models.ResponseSession.responses),
        )
        .where(models.ResponseSession.id == session_id)
    )
    result = await db.execute(query)
    session = result.scalars().unique().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response session not found")
    return session

# --- NEW ENDPOINT: To serve the question bank to the frontend ---
@app.get("/preset-questions", response_model=List[schemas.QuestionCreate], tags=["Employer Flow - Form Builder"])
async def get_preset_questions():
    """
    Returns a list of preset questions for the question bank.
    """
    return BANK_PRESET_QUESTIONS

if __name__ == "__main__":
    print("Starting Uvicorn server...")
    uvicorn.run(app="tasc_main:app", host="0.0.0.0", port=8080, reload=True)