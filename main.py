import uvicorn
import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import ollama
from typing import List
from collections import defaultdict
import json

# Import the modules you've created
import models
import schemas
import database

# --- Application and Database Setup ---

app = FastAPI(
    title="Dynamic Questionnaire API",
    description="A complete API for creating jobs, managing questions with full CRUD, and screening candidates via unique test links.",
    version="1.2.0"
)

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

@app.on_event("startup")
async def startup():
    """
    This function runs when the application starts.
    It drops all existing tables and creates new ones based on the models.
    WARNING: This will delete all data in the database on each restart.
    Remove this for a production environment.
    """
    print("Starting up... Dropping and recreating database tables for development.")
    # async with database.engine.begin() as conn:
    #     await conn.run_sync(models.Base.metadata.drop_all)
    #     await conn.run_sync(models.Base.metadata.create_all)
    print("Database tables created.")

# --- Helper Functions ---

async def get_job_by_id(job_id: int, db: AsyncSession):
    """Helper to fetch a job by its ID, raises 404 if not found."""
    result = await db.execute(select(models.Job).where(models.Job.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with ID {job_id} not found")
    return job

# =======================================================================
#                            EMPLOYER FLOW APIS
# =======================================================================

@app.get("/", tags=["Status"])
async def root():
    return {"message": "Welcome to the Dynamic Questionnaire API"}

# --- Job and Candidate Management ---

@app.post("/jobs/", response_model=schemas.Job, status_code=status.HTTP_201_CREATED, tags=["Employer Flow - Jobs"])
async def create_job(job: schemas.JobCreate, db: AsyncSession = Depends(database.get_db)):
    db_job = models.Job(title=job.title, description=job.description)
    db.add(db_job)
    
    await db.flush()
    new_job_id = db_job.id
    
    await db.commit()
    
    query = (
        select(models.Job)
        .options(
            selectinload(models.Job.questions).selectinload(models.Question.options)
        )
        .where(models.Job.id == new_job_id)
    )
    result = await db.execute(query)
    final_job = result.scalars().unique().first()

    return final_job
    
@app.get("/jobs/{job_id}", response_model=schemas.Job, tags=["Employer Flow"])
async def read_job(job_id: int, db: AsyncSession = Depends(database.get_db)):
    """Retrieves a single job by its ID, including its associated questions."""
    query = (
        select(models.Job)
        .options(
            selectinload(models.Job.questions).selectinload(models.Question.options)
        )
        .where(models.Job.id == job_id)
    )
    result = await db.execute(query)
    job = result.scalars().unique().first() # Use .unique()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/candidates/", response_model=schemas.Candidate, status_code=status.HTTP_201_CREATED, tags=["Employer Flow"])
async def create_candidate(candidate: schemas.CandidateCreate, db: AsyncSession = Depends(database.get_db)):
    db_candidate = models.Candidate(**candidate.model_dump())
    db.add(db_candidate)
    await db.commit()
    await db.refresh(db_candidate)
    return db_candidate

# --- Question Generation and Full CRUD Management ---

@app.get("/jobs/", response_model=List[schemas.Job], tags=["Employer Flow - Jobs"])
async def list_jobs(db: AsyncSession = Depends(database.get_db)):
    """NEW: Retrieves a list of all jobs in the system."""
    # [FIX] Apply the same nested eager loading pattern as in read_job.
    query = (
        select(models.Job)
        .options(
            selectinload(models.Job.questions).selectinload(models.Question.options)
        )
    )
    result = await db.execute(query)
    jobs = result.scalars().unique().all()
    return jobs

@app.get("/jobs/{job_id}/questions", response_model=List[schemas.Question], tags=["Employer Flow"])
async def get_questions_for_job(job_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    NEW: Retrieves all questions (and their options) associated with a specific job.
    This is essential for the employer to view and manage questions.
    """
    # Ensure the job exists first
    await get_job_by_id(job_id, db)
    
    # Query for questions related to the job_id, and eager-load the options
    query = (
        select(models.Question)
        .options(selectinload(models.Question.options))
        .where(models.Question.job_id == job_id)
    )
    result = await db.execute(query)
    questions = result.scalars().all()
    
    return questions

@app.patch("/jobs/{job_id}", response_model=schemas.Job, tags=["Employer Flow - Jobs"])
async def update_job(job_id: int, job_update: schemas.JobUpdate, db: AsyncSession = Depends(database.get_db)):
    """NEW: Edits a job's title or description."""
    # [FIX] Eagerly load relationships before updating.
    query = (
        select(models.Job)
        .options(selectinload(models.Job.questions).selectinload(models.Question.options))
        .where(models.Job.id == job_id)
    )
    result = await db.execute(query)
    db_job = result.scalars().unique().first()
    
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = job_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job, key, value)
        
    await db.commit()
    # The db_job object is already fully loaded, no refresh needed.
    return db_job

@app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow - Jobs"])
async def delete_job(job_id: int, db: AsyncSession = Depends(database.get_db)):
    """NEW: Deletes a job."""
    db_job = await db.get(models.Job, job_id)
    if db_job:
        await db.delete(db_job)
        await db.commit()
    return

@app.post("/jobs/{job_id}/generate-jd-questions/", response_model=List[schemas.Question], tags=["Employer Flow"])
async def generate_and_store_jd_questions(job_id: int, db: AsyncSession = Depends(database.get_db)):
    if not ollama_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ollama service is not available.")
    
    job = await get_job_by_id(job_id, db)
    
    # --- SOLUTION: A NEW, MORE PRECISE PROMPT ---
    # This prompt strictly instructs the model to return only a JSON string.
    # Providing an example (few-shot prompting) makes it much more reliable.
    prompt = f"""
Based on the following job description, generate 5 relevant text-based screening questions for a potential candidate.

**IMPORTANT INSTRUCTIONS:**
- You MUST return ONLY a valid JSON array of objects.
- Each object in the array must have a single key named "question_text".
- Do NOT include any introductory text, explanations, numbering, or markdown in your response. The response must be a raw JSON string.

**EXAMPLE FORMAT:**
[
    {{"question_text": "What is your experience with FastAPI?"}},
    {{"question_text": "Describe a complex project you built using SQLAlchemy."}}
]

**JOB DESCRIPTION:**
{job.description}
"""

    try:
        response = ollama_client.chat(model="llama3.1:8b", messages=[{"role": "user", "content": prompt}])
        content_string = response['message']['content']
        
        # --- NEW: PARSE THE JSON RESPONSE AND EXTRACT QUESTIONS ---
        question_texts = []
        try:
            # Parse the JSON string from the model
            parsed_data = json.loads(content_string)
            # Ensure the data is a list
            if isinstance(parsed_data, list):
                # Extract the text from each dictionary in the list
                question_texts = [
                    item['question_text'] for item in parsed_data 
                    if isinstance(item, dict) and 'question_text' in item and item['question_text'].strip()
                ]
            else:
                 print("Warning: Ollama returned valid JSON, but it was not a list.")

        except (json.JSONDecodeError, TypeError) as e:
            # This is a fallback in case the model ignores instructions and returns plain text.
            # You could add more sophisticated parsing here if needed.
            print(f"Warning: Could not parse JSON from Ollama. Error: {e}. Falling back to line splitting.")
            question_texts = [line.strip() for line in content_string.split('\n') if '?' in line]


        if not question_texts:
             raise HTTPException(status_code=500, detail="Failed to generate or parse questions from AI model.")

        # --- Create, Commit, and Re-Query (the robust pattern we established) ---
        
        new_questions = [
            models.Question(
                job_id=job.id, 
                question_text=q_text, 
                question_type=models.QuestionType.TEXT, 
                is_jd_specific=True
            ) for q_text in question_texts
        ]
        
        db.add_all(new_questions)
        await db.flush()
        new_question_ids = [q.id for q in new_questions]
        await db.commit()

        query = (
            select(models.Question)
            .options(selectinload(models.Question.options))
            .where(models.Question.id.in_(new_question_ids))
        )
        result = await db.execute(query)
        final_questions = result.scalars().all()
        
        return final_questions

    except Exception as e:
        await db.rollback()
        # Propagate specific HTTP exceptions, otherwise raise a generic 500
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An unexpected error occurred: {str(e)}"
        )
        
@app.post("/jobs/{job_id}/questions/text", response_model=schemas.Question, status_code=status.HTTP_201_CREATED, tags=["Employer Flow"])
async def create_text_question(job_id: int, question_data: schemas.QuestionCreate, db: AsyncSession = Depends(database.get_db)):
    await get_job_by_id(job_id, db)
    if question_data.question_type != models.QuestionType.TEXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This endpoint only accepts questions of type 'TEXT'.")
    
    # Step 1: Create the new question object
    db_question = models.Question(job_id=job_id, **question_data.model_dump(exclude={"options"}))
    db.add(db_question)
    await db.flush()  # Use flush to assign an ID to db_question without ending the transaction
    
    new_question_id = db_question.id # Get the ID of the new question
    
    await db.commit() # Commit the transaction to save it permanently

    # Step 2: Perform a clean, separate query to fetch the newly created object
    # This completely avoids any 'expired state' or lazy-loading issues.
    query = (
        select(models.Question)
        .options(selectinload(models.Question.options)) # Eagerly load options
        .where(models.Question.id == new_question_id)
    )
    result = await db.execute(query)
    final_question = result.scalars().first()

    return final_question

@app.post("/jobs/{job_id}/questions/mcq", response_model=schemas.Question, status_code=status.HTTP_201_CREATED, tags=["Employer Flow"])
async def create_mcq_question(job_id: int, question_data: schemas.QuestionCreate, db: AsyncSession = Depends(database.get_db)):
    await get_job_by_id(job_id, db)
    if question_data.question_type not in [models.QuestionType.MCQ_SINGLE, models.QuestionType.MCQ_MULTIPLE]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Question type must be 'MCQ_SINGLE' or 'MCQ_MULTIPLE'.")
    if not question_data.options or len(question_data.options) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "MCQs must have at least two options.")
    
    # Step 1: Create the new question object with its options
    db_question = models.Question(
        job_id=job_id,
        question_text=question_data.question_text,
        question_type=question_data.question_type,
        is_mandatory=question_data.is_mandatory,
        options=[models.QuestionOption(option_text=opt.option_text) for opt in question_data.options]
    )
    db.add(db_question)
    await db.flush() # Assign an ID to the question and its options
    
    new_question_id = db_question.id
    
    await db.commit() # Save everything

    # Step 2: Perform a clean re-fetch
    query = (
        select(models.Question)
        .options(selectinload(models.Question.options)) # Eagerly load the options we just made
        .where(models.Question.id == new_question_id)
    )
    result = await db.execute(query)
    final_question = result.scalars().first()

    return final_question

@app.patch("/questions/{question_id}", response_model=schemas.Question, tags=["Employer Flow"])
async def update_question(question_id: int, question_update: schemas.QuestionUpdate, db: AsyncSession = Depends(database.get_db)):
    # Step 1: Get the existing question from the database.
    # We don't need to eager load here since we are just updating scalar fields.
    db_question = await db.get(models.Question, question_id)
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Step 2: Apply the updates from the request data.
    update_data = question_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_question, key, value)
        
    # Step 3: Commit the changes to the database.
    await db.commit()
    
    # Step 4: Perform a clean, separate query to re-fetch the updated object
    # with all its relationships eagerly loaded for the response.
    query = (
        select(models.Question)
        .options(selectinload(models.Question.options)) # Eagerly load options
        .where(models.Question.id == question_id)
    )
    result = await db.execute(query)
    updated_question = result.scalars().first()

    return updated_question

@app.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow"])
async def delete_question(question_id: int, db: AsyncSession = Depends(database.get_db)):
    db_question = await db.get(models.Question, question_id)
    if db_question:
        await db.delete(db_question)
        await db.commit()
    return

@app.post("/questions/{question_id}/options", response_model=schemas.QuestionOption, status_code=status.HTTP_201_CREATED, tags=["Employer Flow"])
async def add_option_to_question(question_id: int, option_data: schemas.QuestionOptionCreate, db: AsyncSession = Depends(database.get_db)):
    db_question = await db.get(models.Question, question_id)
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    if db_question.question_type not in [models.QuestionType.MCQ_SINGLE, models.QuestionType.MCQ_MULTIPLE]:
        raise HTTPException(status_code=400, detail="Options can only be added to MCQ questions.")

    new_option = models.QuestionOption(question_id=question_id, option_text=option_data.option_text)
    db.add(new_option)
    await db.flush()
    new_option_id = new_option.id
    await db.commit()

    # Re-fetch the newly created option
    final_option = await db.get(models.QuestionOption, new_option_id)
    return final_option

@app.get("/jobs/{job_id}/sessions", response_model=List[schemas.ScreeningSession], tags=["Employer Flow - Jobs"])
async def get_sessions_for_job(job_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Retrieves a list of all screening sessions associated with a specific job.
    """
    # Query for sessions related to the job_id
    query = (
        select(models.ScreeningSession)
        .where(models.ScreeningSession.job_id == job_id)
        .order_by(models.ScreeningSession.created_at.desc()) # Show newest first
    )
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return sessions

@app.patch("/options/{option_id}", response_model=schemas.QuestionOption, tags=["Employer Flow"])
async def update_option(option_id: int, option_update: schemas.QuestionOptionUpdate, db: AsyncSession = Depends(database.get_db)):
    db_option = await db.get(models.QuestionOption, option_id)
    if not db_option:
        raise HTTPException(status_code=404, detail="Option not found")
    
    update_data = option_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_option, key, value)
    await db.commit()
    await db.refresh(db_option)
    return db_option

@app.delete("/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow"])
async def delete_option(option_id: int, db: AsyncSession = Depends(database.get_db)):
    db_option = await db.get(models.QuestionOption, option_id)
    if db_option:
        await db.delete(db_option)
        await db.commit()
    return

@app.get("/candidates/", response_model=List[schemas.Candidate], tags=["Employer Flow - Candidates"])
async def list_candidates(db: AsyncSession = Depends(database.get_db)):
    """NEW: Retrieves a list of all candidates."""
    result = await db.execute(select(models.Candidate))
    candidates = result.scalars().all()
    return candidates

@app.patch("/candidates/{candidate_id}", response_model=schemas.Candidate, tags=["Employer Flow - Candidates"])
async def update_candidate(candidate_id: int, candidate_update: schemas.CandidateUpdate, db: AsyncSession = Depends(database.get_db)):
    """NEW: Edits a candidate's name or email."""
    db_candidate = await db.get(models.Candidate, candidate_id)
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    update_data = candidate_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_candidate, key, value)
        
    await db.commit()
    await db.refresh(db_candidate)
    return db_candidate

@app.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow - Candidates"])
async def delete_candidate(candidate_id: int, db: AsyncSession = Depends(database.get_db)):
    """NEW: Deletes a candidate."""
    db_candidate = await db.get(models.Candidate, candidate_id)
    if db_candidate:
        await db.delete(db_candidate)
        await db.commit()
    return

# --- Session Creation (Final Step for Employer) ---

@app.post("/screening-sessions/", response_model=schemas.ScreeningSessionCreationResponse, status_code=status.HTTP_201_CREATED, tags=["Employer Flow"])
async def create_screening_session(session_data: schemas.ScreeningSessionCreate, db: AsyncSession = Depends(database.get_db)):
    await get_job_by_id(session_data.job_id, db)
    
    # Step 1: Create the session object and add it
    db_session = models.ScreeningSession(job_id=session_data.job_id)
    db.add(db_session)
    
    # Step 2: Flush to get the ID without closing the transaction
    await db.flush()
    
    # --- NEW: Save the ID to a separate variable ---
    new_session_id = db_session.id 

    candidate_links = []
    for cid in session_data.candidate_ids:
        candidate = await db.get(models.Candidate, cid)
        if not candidate:
            # Rollback transaction if a candidate is not found
            await db.rollback() 
            raise HTTPException(status_code=404, detail=f"Candidate with ID {cid} not found")
        
        session_candidate_link = models.SessionCandidate(
            session_id=new_session_id, # Use the saved ID here
            candidate_id=cid
        )
        db.add(session_candidate_link)
        await db.flush()
        # No need to refresh here, we just need the token

        candidate_links.append(schemas.ScreeningSessionLink(
            candidate_id=candidate.id,
            candidate_email=candidate.email,
            access_token=session_candidate_link.access_token
        ))

    # Step 3: Commit the transaction
    await db.commit()

    # Step 4: Build the response using the safe variable, not the expired object
    return schemas.ScreeningSessionCreationResponse(
        session_id=new_session_id, # <-- Use the safe variable
        job_id=session_data.job_id, # We already have this from the request
        candidate_links=candidate_links
    )

@app.get("/screening-sessions/{session_id}/results", response_model=schemas.ScreeningResults, tags=["Employer Flow - Screening"])
async def get_screening_results(session_id: int, db: AsyncSession = Depends(database.get_db)):
    """NEW: Retrieves a full report of all candidate answers for a screening session."""
    query = (
        select(models.ScreeningSession)
        .options(
            selectinload(models.ScreeningSession.job),
            selectinload(models.ScreeningSession.responses).selectinload(models.Response.candidate),
            selectinload(models.ScreeningSession.responses).selectinload(models.Response.question),
            selectinload(models.ScreeningSession.responses).selectinload(models.Response.selected_options)
        )
        .where(models.ScreeningSession.id == session_id)
    )
    result = await db.execute(query)
    session = result.scalars().first()

    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found")

    # Use a dictionary to group responses by candidate for easy processing
    candidate_results_map = defaultdict(lambda: {"responses": []})
    for response in session.responses:
        candidate = response.candidate
        # Store candidate info if not already stored
        if "candidate_id" not in candidate_results_map[candidate.id]:
            candidate_results_map[candidate.id].update({
                "candidate_id": candidate.id,
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "email": candidate.email,
            })
        
        # Format the answer
        answer = schemas.AnswerResult(
            question_text=response.question.question_text,
            question_type=response.question.question_type,
            response_text=response.response_text,
            selected_options=response.selected_options
        )
        candidate_results_map[candidate.id]["responses"].append(answer)

    return schemas.ScreeningResults(
        session_id=session.id,
        job_id=session.job.id,
        job_title=session.job.title,
        results=list(candidate_results_map.values())
    )
# =======================================================================
#                            CANDIDATE FLOW APIS
# =======================================================================

@app.get("/take-test/{access_token}", response_model=schemas.ScreeningTestPayload, tags=["Candidate Flow"])
async def get_test_for_candidate(access_token: str, db: AsyncSession = Depends(database.get_db)):
    query = (
        select(models.SessionCandidate)
        .options(
            selectinload(models.SessionCandidate.session)
            .selectinload(models.ScreeningSession.job)
            .selectinload(models.Job.questions)
            .selectinload(models.Question.options)
        )
        .where(models.SessionCandidate.access_token == access_token)
    )
    result = await db.execute(query)
    link = result.scalars().first()

    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired test link.")

    job = link.session.job
    return schemas.ScreeningTestPayload(
        job_title=job.title,
        job_description=job.description,
        candidate_id=link.candidate_id,
        session_id=link.session_id,
        questions=job.questions
    )

@app.post("/submit-response", response_model=schemas.Response, tags=["Candidate Flow"])
async def submit_response(response_data: schemas.ResponseCreate, db: AsyncSession = Depends(database.get_db)):
    # Query for the question to validate options
    question_query = select(models.Question).options(selectinload(models.Question.options)).where(models.Question.id == response_data.question_id)
    question = (await db.execute(question_query)).scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    db_response = models.Response(
        session_id=response_data.session_id,
        candidate_id=response_data.candidate_id,
        question_id=response_data.question_id
    )
    
    if question.question_type == models.QuestionType.TEXT:
        db_response.response_text = response_data.response_text
    else:
        if not response_data.selected_option_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected option IDs are required.")
        valid_ids = {opt.id for opt in question.options}
        if not set(response_data.selected_option_ids).issubset(valid_ids):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid option ID provided.")
        # Fetch the option objects to associate them
        options_query = select(models.QuestionOption).where(models.QuestionOption.id.in_(response_data.selected_option_ids))
        options = (await db.execute(options_query)).scalars().all()
        db_response.selected_options.extend(options)

    db.add(db_response)
    await db.flush()
    new_response_id = db_response.id
    await db.commit()

    # Re-fetch the complete response object for the return value
    final_response_query = (
        select(models.Response)
        .options(selectinload(models.Response.selected_options))
        .where(models.Response.id == new_response_id)
    )
    final_response = (await db.execute(final_response_query)).scalars().first()
    
    return final_response


# --- Runnable Main Block ---

if __name__ == "__main__":
    """
    This allows you to run the API directly using `python main.py`.
    The server will be available at http://0.0.0.0:8080.
    """
    print("Starting Uvicorn server...")
    uvicorn.run(app="main:app", host="0.0.0.0", port=8080, reload=True)


# @app.patch("/jobs/{job_id}/questions/reorder", status_code=status.HTTP_204_NO_CONTENT, tags=["Employer Flow"])
# async def reorder_questions(job_id: int, request_data: schemas.QuestionReorderRequest, db: AsyncSession = Depends(database.get_db)):
#     """
#     Receives a list of question IDs in their new order and updates the 'order' field in the database.
#     """
#     # Create a mapping of question_id -> new_order
#     order_mapping = {question_id: index for index, question_id in enumerate(request_data.ordered_ids)}

#     # Fetch all questions for the job at once
#     result = await db.execute(
#         select(models.Question).where(models.Question.job_id == job_id)
#     )
#     questions = result.scalars().all()

#     # Update the order for each question
#     for question in questions:
#         if question.id in order_mapping:
#             question.order = order_mapping[question.id]

#     await db.commit()
#     return

@app.get("/preset-questions/", response_model=List[schemas.QuestionCreate], tags=["Employer Flow"]) # <-- Use QuestionCreate
async def get_preset_questions():
    """
    Returns a hardcoded list of common, reusable questions, including default options for MCQs.
    """
    preset_questions_list = [
        {
            "question_text": "What are your salary expectations?", 
            "question_type": "text"
        },
        {
            "question_text": "Are you legally authorized to work in this country?", 
            "question_type": "mcq_single",
            "options": [{"option_text": "Yes"}, {"option_text": "No"}]
        },
        {
            "question_text": "When is your earliest possible start date?", 
            "question_type": "text"
        },
        {
            "question_text": "How did you hear about this position?", 
            "question_type": "mcq_multiple",
            "options": [{"option_text": "LinkedIn"}, {"option_text": "Company Website"}, {"option_text": "Job Fair"}, {"option_text": "Referral"}]
        },
        {
            "question_text": "Do you now or in the future require visa sponsorship?", 
            "question_type": "mcq_single",
            "options": [{"option_text": "Yes"}, {"option_text": "No"}]
        }
    ]
    return [schemas.QuestionCreate(**q) for q in preset_questions_list]