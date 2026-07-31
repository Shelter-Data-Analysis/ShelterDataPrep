#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 17 14:35:08 2024

@author: michaelm
"""
import pandas as pd

name = 'LA'
problems = """
Internal Transfers (TRANS INT) need to be bridged, but data is unclear
""".strip().split('\n')
print(name, problems) 


_ddir = "/Users/michaelm/Library/CloudStorage/OneDrive-Personal/Journal Physics LOS/PRA/"
ddir = _ddir + 'LA County Open Data full database/'
csv_file = ddir+'Animal_Care_PawStats_Data 20241016.csv'
                           
sampleStart = pd.to_datetime('2019-04-01') # outcomes are from 2018-07-01
sampleEnd = pd.to_datetime('2024-07-31')

datedict = {'indate':'INTAKE_DATE', 'outdate':'OUTCOME_DATE'}
renamedict = dict()
outcome_type = 'OUTCOME_TYPE_GROUP'
intake_type = 'INTAKE_TYPE_GROUP'


csv_columns = [
    "FACILITY","ANIMAL_ID",
    "ANIMAL_GROUP","PRIMARY_BREED","IMPOUND_NO",
    "Intake_Fiscal_Year","INTAKE_TYPE","INTAKE_TYPE_GROUP",
    "Outcome_Fiscal_Year","OUTCOME_TYPE","OUTCOME_TYPE_GROUP",
    "INTAKE_DATE","OUTCOME_DATE","ObjectId" ]

csv_intake_types = [
    "DECEASED",
    "OTHER",
    "OWNER SUR",
    "STRAY",
    "" ]
def getInCodes():
    s = 's' # Stray
    w = 'w' # Owner Surrender
    e = 'e' # Other
    x = 'x' # delete
    d = {"DECEASED":x,
         "OTHER":e,
         "OWNER SUR":w,
         "STRAY":s,
         "":e,
         pd.NA:x}
    return d

csv_outcome_types = [
    "ADOPTION",
    "DIED",
    "ESCAPED",
    "EUTHANASIA",
    "MISSING",
    "OTHER LIVE",
    "RESCUE",
    "RTO",
    "",
    pd.NA]

def getOutCodes():
    R = 'R' # RTO
    A = 'A' # Adoption
    T = 'T' # Transfer
    N = 'N' # Non-LIve 
    I = 'I' # Inventory (still in shelter)
    F = 'F' # Foster
    X = 'X' # to be crossed out
    d ={"ADOPTION":A,
        "DIED":N,
        "ESCAPED":N,
        "EUTHANASIA":N,
        "MISSING":N,
        "OTHER LIVE":T,
        "RESCUE":T,
        "RTO":R,
        "":T,
        pd.NA:T }
    return d

def filterRawData (csv):
    adf = csv.loc[
        (csv['ANIMAL_GROUP']=='DOGS')
        & (csv['INTAKE_TYPE_GROUP'] != 'DECEASED')
        & (pd.to_datetime(csv['INTAKE_DATE']) <= pd.to_datetime(csv['OUTCOME_DATE']))
        ,
        ["INTAKE_TYPE","INTAKE_TYPE_GROUP","OUTCOME_TYPE","OUTCOME_TYPE_GROUP",
         "INTAKE_DATE","OUTCOME_DATE" ]
        ] . rename (columns = renamedict)
    adf.loc[adf['OUTCOME_TYPE']=='UNK9999999', 'OUTCOME_TYPE_GROUP']=pd.NA
    return adf

def setFoster (adf):
    fosters = {'FOSTER','TRANS INT'}
    adf['fostint'] = adf['INTAKE_TYPE'].isin(fosters)
    adf['fostout'] = adf['OUTCOME_TYPE'].isin(fosters) 
    return adf


