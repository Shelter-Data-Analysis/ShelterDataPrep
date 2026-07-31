#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Dec 29 09:38:32 2024

@author: michaelm
"""
import pandas as pd

name = 'OC'

_ddir = "/Users/michaelm/Library/CloudStorage/OneDrive-Personal/Journal Physics LOS/PRA/"
ddir = _ddir + 'Orange County 2018-2024/'
# csv_file = ddir+'24-5928 Intakes and Outcomes 2018 to 20241020_1.csv'
# new file put in on 2025-12-24
csv_file = ddir+'25-5969 Intakes and Outcomes 2018 to 20251002 1.csv'
# a = pd.read_csv(csv_file)                           
sampleStart = pd.to_datetime('2018-07-01') # outcomes are from 2018-01-01
sampleEnd = pd.to_datetime('2024-10-19')

datedict = {'indate':'intake_date', 'outdate':'outcome_date', 'dob':'dob'}
renamedict = {'animal_size':'size'}
outcome_type = 'outcome_type'
intake_type = 'intake_type'

csv_columns = [
    "impound_no", "litter_no", "kennel_no", "intake_tot", "kennel_stat", 
    "Current Status", "animal_id", "blue_tag", "activity_no", "activity_seq", 
    "crossing", "jurisdiction", 
    "intake_type", "intake_subtype", "intake_cond", "owner_source", 
    "os_reason", "intake_by_id", "intake_date", "intake_time", 
    "due_out", "review_date", "hold_notify", 
    "outcome_request", "outcome_type", "outcome_subtype", "outcome_cond", 
    "dose", "dose2", "bottle_no", "tnr_program", "zip_code", "outcome_by_id", 
    "outcome_date", "outcome_time", "price", 
    "intake_receipt_no", "outcome_receipt_no", "location", "userid", "stamp", 
    "animal_name", "sex", "dob", "years_old", "months_old", 
    "animal_type", "primary_breed", "secondary_breed", 
    "primary_color", "secondary_color", "animal_size", 
    "coat", "ears", "nose", "tail", "collar_color", "collar_type", 
    "level", "temperament", "os_network"]


csv_intake_types = [
    'BOARDING',
     'CONFISCATE',
     'DISASTER',
     'DISPO REQ',
     'EUTH REQ',
     'FOSTER',
     'OWNER SUR',
     'RETURN',
     'STRAY',
     'STRAY OWN',
     'TRANSFER',
     'WILD']

def getInCodes():
    s = 's' # Stray
    w = 'w' # Owner Surrender
    e = 'e' # Other
    x = 'x' # delete
    d = {'BOARDING':e,
         'CONFISCATE':e,
         'DISASTER':e,
         'DISPO REQ':x,
         'EUTH REQ':x,
         'FOSTER':e,
         'OWNER SUR':w,
         'RETURN':e,
         'STRAY':s,
         'STRAY OWN':s,
         'TRANSFER':e,
         'WILD':x,
         pd.NA:x}
    return d


csv_outcome_types = [
     'ADOPTION',
     'CELL DOGS',
     'DELETE DUP',
     'DIED',
     'DISPOSAL',
     'ESCAPED',
     'EUTH',
     'FOSTER',
     'FOUND EXP',
     'HOME EXP',
     'LOST EXP',
     'MISSING',
     'RESCU WAIT',
     'RET 2 WILD',
     'RTO',
     'RTO 2 OS',
     'RTO-DEAD',
     'RTO-TMH',
     'SURG SCHED',
     'SURG WAIT',
     'TRANSFER',
     pd.NA]

def getOutCodes():
    R = 'R' # RTO
    A = 'A' # Adoption
    T = 'T' # Transfer
    N = 'N' # Non-LIve 
    I = 'I' # Inventory (still in shelter) # IN-CARE
    F = 'F' # Foster
    X = 'X' # to be crossed out
    d = {'ADOPTION':A,
         'CELL DOGS':T,
         'DELETE DUP':X,
         'DIED':N,
         'DISPOSAL':N,
         'ESCAPED':N,
         'EUTH':N,
         'FOSTER':F,
         'FOUND EXP':X,
         'HOME EXP':X,
         'LOST EXP':X,
         'MISSING':N,
         'RESCU WAIT':T,
         'RET 2 WILD':R,
         'RTO':R,
         'RTO 2 OS':R,
         'RTO-DEAD':N,
         'RTO-TMH':R,
         'SURG SCHED':X,
         'SURG WAIT':X,
         'TRANSFER':T,
         pd.NA:X} 
    return d

def sizeTrans (s):
    if isinstance(s,str):
        s = s[0]
        if s in 'XLMSTP':
            return s
    return 'M'        

# !!! *** THIS Filtering overlaps but does not coincide with 
#       the 'X' outcome and 'x' intake filtering *** !!!
# !!! *** THIS is a potential source of inconsistency 
#       in the data cleaning between the R_tool and the Python-based KM *** !!!
def filterRawData (csv, extracols=[]):
    adf = csv.loc[
        (csv['animal_type'] == 'DOG')
         & ~csv['intake_type'].isin(["DISPO REQ", "FOUND", "LOST", "SURGERY"])
         ## "FOSTER",
         & ~csv['intake_cond'].isin(['DEAD', 'HEAD TEST'])
         & ~csv['outcome_type'].isin(["DOA","DISPOSAL","DELETE DUP",
                                      "HOME EXP","FOUND EXP","LOST EXP"])
         & ~csv['kennel_no'].isin(["FOUND","HOME","HOME EXP","LOST"])
         ,
        ['animal_id','jurisdiction',
         'animal_size', 'dob', # added Feb 2025
         #'outcome_request','zip_code','sex','dob','primary_breed'
         'intake_date','intake_type','intake_subtype','intake_cond',
         'outcome_date','outcome_type','outcome_subtype','outcome_cond']
        + extracols
        ] . rename (columns=renamedict)
    adf.loc[(adf['outcome_type'] == 'ADOPTION') &
            (adf['outcome_subtype'] == 'RESCUE')
            ,
            'outcome_type'] = 'TRANSFER'
#    assert (not (adf['outcome_type'].isna() ^ 
#                 adf['outcome_date'].isna()).any())
    adf['size'] = adf['size'].map(sizeTrans)
    return adf

def setFoster (adf):
    adf['fostint'] = (adf['intake_type'].isin(['F2A','FOSTER','FOSTER-FF']) |
                      adf['intake_subtype'].isin(['F2A','FOSTER','FOSTER-FF'])) 
    adf['fostout'] = adf['outcome_type'] == 'FOSTER'
    return adf



