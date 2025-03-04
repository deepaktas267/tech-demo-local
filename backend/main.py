from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, conint
import jwt
import requests
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List
from sqlalchemy import func
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

# FastAPI App Initialization
app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Change this for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Database Configuration
DATABASE_URL = "mysql+pymysql://demo:bakihanma@localhost/recipe"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Config
SECRET_KEY = "38fbd608face41326ec160e316b0c8cb3b2cd42d4ad3b2852540c16cd7d493be"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 1

# Spoonacular API Key
SPOONACULAR_API_KEY = "4ab74daf499747d6b74b515901e5ecfe"

# User Model
class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(15), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

    favorite_recipes = relationship("FavoriteRecipe", back_populates="user")
    feedbacks = relationship("RecipeFeedback", back_populates="user")

# Favorite Recipes Model
class FavoriteRecipe(Base):
    __tablename__ = "favorite_recipes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    recipe_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    image_url = Column(String(255), nullable=False)
    ingredients = Column(Text, nullable=False)
    nutrition = Column(Text, nullable=False)

    user = relationship("User", back_populates="favorite_recipes")

# Feedback Model
class RecipeFeedback(Base):
    __tablename__ = "recipe_feedback"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    recipe_id = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=False)  # 1 to 5 rating
    comment = Column(Text, nullable=False)

    user = relationship("User", back_populates="feedbacks")

# Create Tables Automatically on Startup
Base.metadata.create_all(bind=engine)

# Dependency: Get Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# JWT Token Generation
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=TOKEN_EXPIRE_HOURS)):
    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        print(f"Generated Token: {token}")  # Debugging Log
        return token
    except Exception as e:
        print(f"JWT Token Generation Error: {e}")
        raise HTTPException(status_code=500, detail="Token generation failed")


# Pydantic Models for Validation
class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    phone: str
    password: str
    re_password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ForgotPasswordRequest(BaseModel):
    username: str
    email: EmailStr
    new_password: str
    re_new_password: str

class RecipeSearchRequest(BaseModel):
    ingredients: str

class FavoriteRecipeRequest(BaseModel):
    user_id: int
    recipe_id: int
    title: str
    image_url: str
    ingredients: str  # JSON string
    nutrition: str  # JSON string

class RecipeFeedbackRequest(BaseModel):
    user_id: int
    recipe_id: int
    rating: conint(ge=1, le=5)  # Rating between 1 and 5
    comment: str

class FeedbackResponse(BaseModel):
    username: str
    recipe_name: str
    recipe_image: str
    rating: int
    comment: str

# Signup Endpoint
@app.post("/signup/")
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    if request.password != request.re_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing_user = db.query(User).filter((User.username == request.username) | (User.email == request.email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = pwd_context.hash(request.password)
    
    # Assign user_id=1 for admin (first registered user)
    user_count = db.query(User).count()
    new_user = User(
        username=request.username,
        email=request.email,
        phone=request.phone,
        password=hashed_password,
    )
    
    if user_count == 0:
        new_user.user_id = 1  # Assign first user as admin

    db.add(new_user)
    db.commit()

    return {"message": "Signup successful", "username": request.username}

@app.post("/login/")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == request.username).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password (User not found)")

        print(f"User found: {user.username}")  # Debugging log

        if not pwd_context.verify(request.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid username or password (Incorrect password)")

        # Debug: Ensure user_id is retrieved correctly
        print(f"User ID: {user.user_id}")

        # Generate Token
        token_data = {"sub": user.username, "user_id": user.user_id}
        print(f"Token Data Before Encoding: {token_data}")
        token = create_access_token(token_data)
        
        print(f"Token generated: {token}")  # Debugging log

        return {
            "message": "Login successful",
            "token": token,
            "username": user.username,
            "user_id": user.user_id
        }
    except Exception as e:
        print(f"Login Error: {e}")  # Log error
        raise HTTPException(status_code=500, detail="Login failed due to server error")



# # Forgot Password Endpoint
@app.post("/forgot-password/")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    if request.new_password != request.re_new_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user = db.query(User).filter(User.username == request.username, User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = pwd_context.hash(request.new_password)
    db.commit()

    return {"message": "Password reset successful"}




# Fetch Recipes from Spoonacular API
@app.post("/recipes/")
def get_recipes(request: RecipeSearchRequest):
    url = f"https://api.spoonacular.com/recipes/findByIngredients?ingredients={request.ingredients}&number=5&apiKey={SPOONACULAR_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error fetching recipes")
    
    recipes = response.json()
    return recipes


@app.get("/recipe/{recipe_id}/")
def get_recipe_details(recipe_id: int, user_ingredients: str = ""):
    # Get full recipe details
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information?includeNutrition=true&apiKey={SPOONACULAR_API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error fetching recipe details")

    data = response.json()

    # Extract preparation steps
    preparation_steps = []
    if "analyzedInstructions" in data and data["analyzedInstructions"]:
        for instruction in data["analyzedInstructions"]:
            for step in instruction.get("steps", []):
                preparation_steps.append(step["step"])

    # Extract all ingredients from the recipe
    all_ingredients = [ingredient["name"].lower() for ingredient in data["extendedIngredients"]]

    # Identify missing ingredients
    user_ingredients_list = [ing.strip().lower() for ing in user_ingredients.split(",")] if user_ingredients else []
    missed_ingredients = [ing for ing in all_ingredients if ing not in user_ingredients_list]

    # Construct response
    recipe_details = {
        "id": data["id"],
        "title": data["title"],
        "image": data["image"],
        "ingredients": all_ingredients,
        "missedIngredients": missed_ingredients,  # Ensure missed ingredients are included
        "instructions": preparation_steps if preparation_steps else data.get("instructions", "No instructions available"),
        "nutrition": [{"name": n["name"], "amount": n["amount"]} for n in data["nutrition"]["nutrients"][:5]],
    }

    return recipe_details



# Save Favorite Recipe
@app.post("/save-recipe/")
def save_recipe(request: FavoriteRecipeRequest, db: Session = Depends(get_db)):
    # Check if the recipe already exists in favorites
    existing_recipe = db.query(FavoriteRecipe).filter(
        FavoriteRecipe.user_id == request.user_id,
        FavoriteRecipe.recipe_id == request.recipe_id
    ).first()

    if existing_recipe:
        raise HTTPException(status_code=400, detail="Recipe already saved")

    # Create new favorite recipe entry
    new_favorite = FavoriteRecipe(
        user_id=request.user_id,
        recipe_id=request.recipe_id,
        title=request.title,
        image_url=request.image_url,
        ingredients=request.ingredients,
        nutrition=request.nutrition
    )

    db.add(new_favorite)
    db.commit()
    db.refresh(new_favorite)

    return {"message": "Recipe saved successfully"}



# Get Saved Recipes for a User
@app.get("/saved-recipes/{user_id}/", response_model=List[FavoriteRecipeRequest])
def get_saved_recipes(user_id: int, db: Session = Depends(get_db)):
    recipes = db.query(FavoriteRecipe).filter(FavoriteRecipe.user_id == user_id).all()
    if not recipes:
        return []  # Return an empty list instead of raising an exception
    return recipes



# Delete a Saved Recipe
@app.delete("/saved-recipes/{user_id}/{recipe_id}/", status_code=200)
def delete_saved_recipe(user_id: int, recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(FavoriteRecipe).filter(
        FavoriteRecipe.user_id == user_id, FavoriteRecipe.recipe_id == recipe_id
    ).first()

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    db.delete(recipe)
    db.commit()
    db.close()  # Ensure the session is closed

    return {"message": "Recipe deleted successfully"}



@app.post("/recipe-feedback/")
def submit_recipe_feedback(request: RecipeFeedbackRequest, db: Session = Depends(get_db)):
    # Check if feedback already exists for the user and recipe
    existing_feedback = db.query(RecipeFeedback).filter(
        RecipeFeedback.user_id == request.user_id,
        RecipeFeedback.recipe_id == request.recipe_id
    ).first()

    if existing_feedback:
        raise HTTPException(status_code=400, detail="You have already submitted feedback for this recipe.")

    # Create and save new feedback
    feedback = RecipeFeedback(
        user_id=request.user_id,
        recipe_id=request.recipe_id,
        rating=request.rating,
        comment=request.comment
    )
    db.add(feedback)
    db.commit()
    
    return {"message": "Feedback submitted successfully"}



# List Users Endpoint (excluding admin user_id=1)
@app.get("/users/")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.user_id != 1).all()
    user_list = [{"username": user.username, "email": user.email, "phone": user.phone} for user in users]
    return {"users": user_list}

@app.get("/most-saved-recipes/", response_model=List[dict])
def get_most_saved_recipes(db: Session = Depends(get_db)):
    recipes = (
        db.query(FavoriteRecipe.title, FavoriteRecipe.image_url, func.count(FavoriteRecipe.recipe_id).label("save_count"))
        .group_by(FavoriteRecipe.recipe_id, FavoriteRecipe.title, FavoriteRecipe.image_url)
        .order_by(func.count(FavoriteRecipe.recipe_id).desc())
        .all()
    )

    return [{"title": recipe.title, "image_url": recipe.image_url} for recipe in recipes]

# Fetch Feedback for a Recipe
@app.get("/feedback-list/", response_model=List[FeedbackResponse])
def get_feedback_list(db: Session = Depends(get_db)):
    feedbacks = db.query(RecipeFeedback).all()
    
    if not feedbacks:
        raise HTTPException(status_code=404, detail="No feedback found")

    feedback_list = []
    for feedback in feedbacks:
        user = db.query(User).filter(User.user_id == feedback.user_id).first()
        recipe = db.query(FavoriteRecipe).filter(FavoriteRecipe.recipe_id == feedback.recipe_id).first()

        if not user or not recipe:
            continue

        feedback_list.append({
            "username": user.username,
            "recipe_name": recipe.title,
            "recipe_image": recipe.image_url,
            "rating": feedback.rating,
            "comment": feedback.comment,
        })

    return feedback_list


@app.get("/popular-recipes/", response_model=List[dict])
def get_popular_recipes(db: Session = Depends(get_db)):
    popular_recipes = (
        db.query(
            RecipeFeedback.recipe_id,
            func.avg(RecipeFeedback.rating).label("average_rating"),
            FavoriteRecipe.title,
            FavoriteRecipe.image_url
        )
        .join(FavoriteRecipe, RecipeFeedback.recipe_id == FavoriteRecipe.recipe_id)
        .group_by(RecipeFeedback.recipe_id, FavoriteRecipe.title, FavoriteRecipe.image_url)
        .having(func.avg(RecipeFeedback.rating) >= 4)
        .all()
    )

    return [
        {
            "recipe_id": recipe.recipe_id,
            "title": recipe.title,
            "image_url": recipe.image_url,
            "average_rating": round(recipe.average_rating, 1)  # Round to 1 decimal
        }
        for recipe in popular_recipes
    ]

