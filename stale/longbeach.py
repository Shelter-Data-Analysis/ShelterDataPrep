#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 17 14:35:08 2024

@author: michaelm
"""
import pandas as pd

name = 'LB'
problems = """
Ended relationship with SPCA-LA
""".strip().split('\n')
print(name, problems)


_ddir = "/Users/michaelm/Library/CloudStorage/OneDrive-Personal/Journal Physics LOS/PRA/"
ddir = _ddir + "Long Beach October 2024/"
csv_file = ddir+'animal-shelter-intakes-and-outcomes.csv'
                           
sampleStart = pd.to_datetime('2018-03-01').date()
sampleEnd = pd.to_datetime('2024-12-31').date()


datedict = {'indate':'Intake Date', 'outdate':'Outcome Date', 'dob':'DOB'}
renamedict = dict()
outcome_type = 'Outcome Type'
intake_type = 'Intake Type'

csv_columns = [
    'Animal ID','Animal Name','Animal Type',
    'Primary Color','Secondary Color','Sex','DOB',
    'Intake Date','Intake Condition',
    'Intake Type','Intake Subtype','Reason for Intake',
    'Outcome Date',
    'Crossing','Jurisdiction',
    'Outcome Type','Outcome Subtype',
    'latitude','longitude',
    'intake_is_dead','outcome_is_dead','was_outcome_alive',
    'geopoint']

csv_intake_types = [
    "Adopted Animal Return",
    "CONFISCATE",
    "Euthenasia Required",
    "FOSTER",
    "OWNER SURRENDER",
    "QUARANTINE",
    "RETURN",
    "SAFE KEEP",
    "STRAY",
    "TRAP, NEUTER, RETURN",
    "WELFARE SEIZED",
    "WILDLIFE" ]

def getInCodes():
    s = 's' # Stray
    w = 'w' # Owner Surrender
    e = 'e' # Other
    x = 'x' # delete
    d = {
        "Adopted Animal Return":w,
        "CONFISCATE":e,
        "Euthenasia Required":x,
        "FOSTER":e,
        "OWNER SURRENDER":w,
        "QUARANTINE":x,
        "RETURN":e,
        "SAFE KEEP":x,
        "STRAY":s,
        "TRAP, NEUTER, RETURN":x,
        "WELFARE SEIZED":e,
        "WILDLIFE":x,
         pd.NA:x}
    return d


csv_outcome_types = [
    "ADOPTION",
    "COMMUNITY CAT",
    "DIED",
    "DISPOSAL",
    "DUPLICATE",
    "EUTHANASIA",
    "FOSTER",
    "FOSTER TO ADOPT",
    "HOMEFIRST",
    "MISSING",
    "RESCUE",
    "RETURN TO OWNER",
    "RETURN TO RESCUE",
    "RETURN TO WILD HABITAT",
    "SHELTER, NEUTER, RETURN",
    "TRANSFER",
    "TRANSPORT",
    "TRAP, NEUTER, RELEASE" ]

def getOutCodes():
    R = 'R' # RTO
    A = 'A' # Adoption
    T = 'T' # Transfer
    N = 'N' # Non-LIve 
    I = 'I' # Inventory (still in shelter)
    F = 'F' # Foster
    X = 'X' # to be crossed out
    d = {'ADOPTION':A,
         'COMMUNITY CAT':X,
         'DIED':N,
         'DISPOSAL':N,
         'DUPLICATE':X, 
         'EUTHANASIA':N, 
         'FOSTER':F, 
         'FOSTER TO ADOPT':A, #  the category with the most entries 
         'HOMEFIRST':A, 
         'MISSING':N, 
         'RESCUE':T, 
         'RETURN TO OWNER':R, 
         'RETURN TO RESCUE':R, 
         "RETURN TO WILD HABITAT":X,
         "SHELTER, NEUTER, RETURN":X,
         'TRANSFER':T, 
         'TRANSPORT':T,
         "TRAP, NEUTER, RELEASE":X }
    return d

def filterRawData (csv):
    adf = csv.loc[
        (csv['Animal Type']=='DOG') & (csv['intake_is_dead'] == 'Alive on Intake')
        & ~csv['Intake Type'].isin({'QUARANTINE', 'SAFE KEEP', 'WILDLIFE', 
                                  'Euthanasia Required'})
        & ~csv['Outcome Type'].isin({'COMMUNITY CAT','DUPLICATE'})
        ,
        ['Animal ID', 'DOB', 'Intake Date', 'Intake Type', 'Intake Subtype',
         'Outcome Date', 'Outcome Type', 'Outcome Subtype', 'outcome_is_dead']
        ] . rename (columns = renamedict)
    return adf

def setFoster (adf):
    adf['fostint'] = (adf['Intake Type'] == 'FOSTER')
    adf['fostout'] = (adf['Outcome Type'] == 'FOSTER')
    return adf


