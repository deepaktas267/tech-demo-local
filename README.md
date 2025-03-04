cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
cd ..
cd frontend
bun/npm install

bun dev / npm run dev
