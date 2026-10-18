import os
import json
from datetime import datetime, date
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from mysql.connector import pooling

app = FastAPI(title="AI Elite Routine & Habit Ecosystem")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MySQL Connection Pool
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "admin@123",  # Apna MySQL password yahan daalein
    "database": "ai_dynamic_app",
    "pool_name": "mypool",
    "pool_size": 15
}

try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(**db_config)
except Exception as e:
    print(f"Database pool setup failed: {e}")

def get_db():
    conn = db_pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()

# ----------------- Database Schema Init -----------------
def init_db():
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    
    # 1. Users Table (Gamification, XP, Levels, Streak)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        phone VARCHAR(15) UNIQUE NOT NULL,
        otp VARCHAR(6),
        name VARCHAR(100),
        email VARCHAR(100),
        age INT,
        goal VARCHAR(255),
        xp_points INT DEFAULT 0,
        streak_count INT DEFAULT 0,
        last_active_date DATE,
        squad_id INT DEFAULT NULL,
        is_registered BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Habits / Tasks Table (Time of day, Category, Frequency)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habits (
        id INT AUTO_INCREMENT PRIMARY KEY,
        phone VARCHAR(15),
        title VARCHAR(255) NOT NULL,
        category VARCHAR(50) DEFAULT 'General',
        time_of_day VARCHAR(20) DEFAULT 'Morning', -- Morning, Afternoon, Evening
        frequency VARCHAR(20) DEFAULT 'Daily',     -- Daily, Weekly
        is_completed BOOLEAN DEFAULT FALSE,
        created_date DATE,
        completed_at TIMESTAMP NULL
    )
    """)

    # 3. Badges / Achievements Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_badges (
        id INT AUTO_INCREMENT PRIMARY KEY,
        phone VARCHAR(15),
        badge_name VARCHAR(100),
        badge_icon VARCHAR(50),
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. Squads Table (Social Accountability with Friends)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS squads (
        id INT AUTO_INCREMENT PRIMARY KEY,
        squad_name VARCHAR(100) UNIQUE NOT NULL,
        created_by VARCHAR(15),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Daily Journal / Mood Log Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS journals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        phone VARCHAR(15),
        mood VARCHAR(50),
        note TEXT,
        log_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 6. AI Chat Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        phone VARCHAR(15),
        sender VARCHAR(10),
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()

@app.on_event("startup")
def on_startup():
    init_db()

# ----------------- Pydantic Schemas -----------------
class OTPRequest(BaseModel):
    phone: str

class OTPVerify(BaseModel):
    phone: str
    otp: str

class ProfileRequest(BaseModel):
    phone: str
    name: str
    email: str
    age: int

class SurveyRequest(BaseModel):
    phone: str
    goal: str

class HabitCreateRequest(BaseModel):
    phone: str
    title: str
    category: str
    time_of_day: str  # Morning, Afternoon, Evening

class HabitToggleRequest(BaseModel):
    habit_id: int
    is_completed: bool

class JournalRequest(BaseModel):
    phone: str
    mood: str
    note: str

class SquadCreateRequest(BaseModel):
    phone: str
    squad_name: str

class SquadJoinRequest(BaseModel):
    phone: str
    squad_name: str

class AIChatRequest(BaseModel):
    phone: str
    message: str

# ----------------- API Endpoints -----------------

@app.post("/api/auth/send-otp")
def send_otp(req: OTPRequest, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    otp = "123456"
    cursor.execute("SELECT * FROM users WHERE phone = %s", (req.phone,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("INSERT INTO users (phone, otp) VALUES (%s, %s)", (req.phone, otp))
    else:
        cursor.execute("UPDATE users SET otp = %s WHERE phone = %s", (otp, req.phone))
    
    conn.commit()
    cursor.close()
    return {"status": "success", "message": "OTP sent successfully (Use 123456)"}

@app.post("/api/auth/verify-otp")
def verify_otp(req: OTPVerify, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE phone = %s AND otp = %s", (req.phone, req.otp))
    user = cursor.fetchone()
    cursor.close()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    return {
        "status": "success",
        "is_registered": bool(user["is_registered"]),
        "has_goal": bool(user["goal"])
    }

@app.post("/api/profile/save")
def save_profile(req: ProfileRequest, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET name=%s, email=%s, age=%s, is_registered=TRUE WHERE phone=%s",
        (req.name, req.email, req.age, req.phone)
    )
    conn.commit()
    cursor.close()
    return {"status": "success", "message": "Profile saved successfully"}

@app.post("/api/survey/submit")
def submit_survey(req: SurveyRequest, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET goal=%s WHERE phone=%s", (req.goal, req.phone))
    
    today = date.today()
    # Market apps default starter habits split by time of day
    default_habits = [
        ("Morning Hydration & Sunshine", "Health", "Morning"),
        (f"Deep Focus Work: {req.goal}", "Productivity", "Afternoon"),
        ("15 Min Reading / Skill Building", "Growth", "Evening")
    ]
    
    for title, cat, time_slot in default_habits:
        cursor.execute(
            "INSERT INTO habits (phone, title, category, time_of_day, created_date) VALUES (%s, %s, %s, %s, %s)",
            (req.phone, title, cat, time_slot, today)
        )
        
    conn.commit()
    cursor.close()
    return {"status": "success", "message": "Elite habits & routine initialized!"}

@app.get("/api/dashboard/{phone}")
def get_dashboard(phone: str, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT name, goal, xp_points, streak_count, squad_id FROM users WHERE phone = %s", (phone,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    today = date.today()
    cursor.execute("SELECT * FROM habits WHERE phone = %s AND created_date = %s", (phone, today))
    habits = cursor.fetchall()
    
    # Fetch Badges
    cursor.execute("SELECT badge_name, badge_icon FROM user_badges WHERE phone = %s", (phone,))
    badges = cursor.fetchall()

    # Level Calculation
    xp = user["xp_points"]
    level = "Beginner 🌿"
    if xp >= 300: level = "Elite Achiever ⭐"
    if xp >= 700: level = "Habit Master 🔥"

    cursor.close()
    return {
        "user": {
            "name": user["name"],
            "goal": user["goal"],
            "xp_points": xp,
            "streak_count": user["streak_count"],
            "level": level,
            "squad_id": user["squad_id"]
        },
        "habits": habits,
        "badges": badges
    }

@app.post("/api/habits/add")
def add_habit(req: HabitCreateRequest, conn=Depends(get_db)):
    cursor = conn.cursor()
    today = date.today()
    cursor.execute(
        "INSERT INTO habits (phone, title, category, time_of_day, created_date) VALUES (%s, %s, %s, %s, %s)",
        (req.phone, req.title, req.category, req.time_of_day, today)
    )
    conn.commit()
    cursor.close()
    return {"status": "success", "message": "Custom habit added successfully"}

@app.post("/api/habits/update")
def update_habit(req: HabitToggleRequest, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT phone, is_completed FROM habits WHERE id = %s", (req.habit_id,))
    habit = cursor.fetchone()
    
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
        
    phone = habit["phone"]
    cursor.execute(
        "UPDATE habits SET is_completed = %s, completed_at = CURRENT_TIMESTAMP WHERE id = %s",
        (req.is_completed, req.habit_id)
    )
    
    # Gamification & Milestone Check
    if req.is_completed and not habit["is_completed"]:
        cursor.execute("UPDATE users SET xp_points = xp_points + 25 WHERE phone = %s", (phone,))
        
        today = date.today()
        cursor.execute("SELECT last_active_date, streak_count, xp_points FROM users WHERE phone = %s", (phone,))
        u = cursor.fetchone()
        
        if u["last_active_date"] != today:
            new_streak = u["streak_count"] + 1
            cursor.execute(
                "UPDATE users SET streak_count = %s, last_active_date = %s WHERE phone = %s",
                (new_streak, today, phone)
            )
            # Automatic Badge Unlock Example for 3-day streak
            if new_streak == 3:
                cursor.execute(
                    "INSERT IGNORE INTO user_badges (phone, badge_name, badge_icon) VALUES (%s, '3-Day Fire Streak', '🔥')",
                    (phone,)
                )

    conn.commit()
    cursor.close()
    return {"status": "success", "message": "Habit status updated & XP credited!"}

@app.post("/api/journal/save")
def save_journal(req: JournalRequest, conn=Depends(get_db)):
    cursor = conn.cursor()
    today = date.today()
    cursor.execute(
        "INSERT INTO journals (phone, mood, note, log_date) VALUES (%s, %s, %s, %s)",
        (req.phone, req.mood, req.note, today)
    )
    conn.commit()
    cursor.close()
    return {"status": "success", "message": "Daily reflection saved!"}

@app.post("/api/squads/create")
def create_squad(req: SquadCreateRequest, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("INSERT INTO squads (squad_name, created_by) VALUES (%s, %s)", (req.squad_name, req.phone))
        squad_id = cursor.lastrowid
        cursor.execute("UPDATE users SET squad_id = %s WHERE phone = %s", (squad_id, req.phone))
        conn.commit()
    except Exception:
        raise HTTPException(status_code=400, detail="Squad name already exists.")
    cursor.close()
    return {"status": "success", "message": f"Squad '{req.squad_name}' created successfully!"}

@app.get("/api/squads/leaderboard/{squad_id}")
def squad_leaderboard(squad_id: int, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, streak_count, xp_points FROM users WHERE squad_id = %s ORDER BY streak_count DESC", (squad_id,))
    members = cursor.fetchall()
    cursor.close()
    return {"squad_id": squad_id, "members": members}

@app.post("/api/ai/chat")
def ai_chat(req: AIChatRequest, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_logs (phone, sender, message) VALUES (%s, 'user', %s)", (req.phone, req.message))
    
    msg = req.message.lower()
    if "tired" in msg or "burnout" in msg:
        reply = "Aapka body rest maang raha hai. Aaj light habits complete karo aur jaldi so jao. Consistency is a marathon, not a sprint! 💙"
    elif "procrastinate" in msg:
        reply = "Sirf 2 minute rule try karo: Sirf 2 minute ke liye task shuru karo, inertia apne aap tut jayega! ⚡"
    else:
        reply = f"AI Coach: '{req.message}' — Brilliant observation! Apne goal ki taraf ek aur chota kadam aaj zaroor lo. 🚀"

    cursor.execute("INSERT INTO chat_logs (phone, sender, message) VALUES (%s, 'ai', %s)", (req.phone, reply))
    conn.commit()
    cursor.close()
    return {"reply": reply}