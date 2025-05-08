from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .models import EdfDataPoint
from .database import SessionLocal, Base, engine
import mne
import tempfile
import os

# Создаём таблицы при запуске (если их нет)
Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the EDF uploader service!"}

@app.get("/test-db")
def test_db():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT version()")).first()
        return {"status": "Database connected", "version": result[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/upload-edf/")
async def upload_edf(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        if not file.filename.endswith('.edf'):
            raise HTTPException(status_code=400, detail="Only .edf files are allowed")

        # Ограничиваем размер файла (например, до 10 МБ)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
        edf_data = await file.read()
        if len(edf_data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".edf") as tmpfile:
            tmpfile.write(edf_data)
            tmpfile_path = tmpfile.name

        try:
            # Читаем через MNE
            raw = mne.io.read_raw_edf(tmpfile_path, preload=True)
            data, times = raw[:, :]

            # Очистка старых данных (для тестирования)
            db.query(EdfDataPoint).delete()
            db.commit()

            # Сохраняем в БД
            for ch_idx, ch_name in enumerate(raw.ch_names):
                for t_idx, t in enumerate(times):
                    db_record = EdfDataPoint(
                        channel=ch_name,
                        time=float(t),
                        value=float(data[ch_idx, t_idx])
                    )
                    db.add(db_record)
            db.commit()

            return {
                "message": f"{file.filename} uploaded and saved to DB",
                "channels": raw.ch_names,
                "total_records": len(raw.ch_names) * len(times)
            }

        finally:
            # Удаляем временный файл
            os.unlink(tmpfile_path)

    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@app.get("/get-all-data")
def get_all_data():
    db = SessionLocal()
    try:
        results = db.query(EdfDataPoint).all()
        return [{
            "id": r.id,
            "channel": r.channel,
            "time": r.time,
            "value": r.value
        } for r in results]
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()