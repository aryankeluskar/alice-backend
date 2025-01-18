import json
import re
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import requests
from scholarly import scholarly

from dotenv import load_dotenv
load_dotenv()
import os


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/search")
def search(query: str):
    search_query = scholarly.search_pubs(query)
    res = next(search_query)

    print(res.keys())
    print(type(res))

    # return res
    

    final_res = {
        "title": res["bib"]["title"],
        "authors": ", ".join(res["bib"]["author"]),
        "abstract": res["bib"]["abstract"],
        "year": res["bib"]["pub_year"],
        "url": res["pub_url"]
    }
    return final_res