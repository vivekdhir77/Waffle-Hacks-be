# Flash Focus: Consume less. Study more. One card at a time. 

- Upload notes, get flash cards, avoid distractions and ace your exams.

## Inspiration

In today's world, students are constantly distracted by platforms like YouTube, Instagram, and TikTok. The addictive nature of short-form videos makes it tough to stay focused during periods of deep work Eg. exam periods. As students who have dealt with these struggles ourselves, we decided to create a solution. Our goal is to not only block these distractions but also transform them into chances for learning.

## What it does

Flash Focus is a Chrome extension that:
- Blocks user-specified websites during crucial exam periods
- Uses AI to identify and block websites irrelevant to the student's syllabus
- Converts attempted visits to restricted sites into study sessions
- Presents flashcards based on the student's exam notes when distractions are attempted
- Allows users to create custom flashcards for additional study material
- Displays a countdown to the exam date after incorrect answers, reinforcing urgency to go back and focus.

## How we built it

Our tech stack includes:
- Frontend: React, TypeScript, Vite, and Tailwind CSS
- Backend: Python, FastAPI
- Database: MongoDB
- AI Integration: Gemini API

# how to run

- Create virtual environment
- pip install -r requirements.txt
- Fill in environment variables (GOOGLE_API_KEY, JWT_SECRET, JWT_EXPIRE_TIME & MongoDB_CONNECT)
- > python3 main.py