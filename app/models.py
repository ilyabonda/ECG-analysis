from sqlalchemy import Column, Integer, String, Float
from .database import Base

class EdfDataPoint(Base):
    __tablename__ = "edf_data_points"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, index=True)   
    time = Column(Float)                  
    value = Column(Float)                  