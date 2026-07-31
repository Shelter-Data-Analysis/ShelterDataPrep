#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 28 09:19:05 2024

@author: michaelm
"""

import pandas as pd

name = 'IR'

_ddir = "/Users/michaelm/Library/CloudStorage/OneDrive-Personal/Journal Physics LOS/PRA/"
ddir = _ddir + "Irvine/"
csv_file = ddir+'IrvineDogs.csv'

sampleStart = pd.to_datetime('2014-07-01').date()
sampleEnd = pd.to_datetime('2024-10-14').date()

datedict = {'indate':'intake_date', 'outdate':'outcome_date'}
renamedict = dict()
outcome_type = 'outcome_type'
intake_type = 'intake_type'

csv_columns = [
    'animal_id','crossing','jurisdiction',
    'intake_type','intake_subtype','intake_date','intake_cond',
    'outcome_type','outcome_subtype','outcome_date',
    'impound_no','outcome_cond' ]

csv_intake_types = [
    'EUTH REQ',
    'FOSTER',
    'IACC-BIRTH',
    'OWNER SUR',
    'POLICEHOLD',
    'RETURN',
    'SAFEKEEP',
    'STRAY',
    'TRANSFER' ]

def getInCodes():
    s = 's' # Stray
    w = 'w' # Owner Surrender
    e = 'e' # Other
    x = 'x' # delete
    d = {'EUTH REQ':x,
        'FOSTER':e,
        'IACC-BIRTH':e,
        'OWNER SUR':w,
        'POLICEHOLD':e,
        'RETURN':e,
        'SAFEKEEP':e,
        'STRAY':s,
        'TRANSFER':e,
         pd.NA:x}
    return d


csv_outcome_types = [
    'ADOPT-RES',
    'ADOPTION',
    'DIED',
    'EUTH',
    'EUTH OR',
    'EUTH VET',
    'FOSTER',
    'MISSING',
    'RTO',
    'RTO-FIELD',
    'TRANSFER' ]

def getOutCodes():
    R = 'R' # RTO
    A = 'A' # Adoption
    T = 'T' # Transfer
    N = 'N' # Non-LIve 
    I = 'I' # Inventory (still in shelter)
    F = 'F' # Foster
    X = 'X' # to be crossed out
    d = {'ADOPT-RES':A,
        'ADOPTION':A,
        'DIED':N,
        'EUTH':N,
        'EUTH OR':X,
        'EUTH VET':N,
        'FOSTER':F,
        'MISSING':N,
        'RTO':R,
        'RTO-FIELD':R,
        'TRANSFER':T }
    return d

def filterRawData (csv):
    adf = csv.loc[
        ## already limited this dataset to DOGS !!!!!!!!!!
        (~csv['intake_type'].isin({'DEAD','DISPO REQ','EUTH REQ',
                                   'POLICE HOLD','SAFEKEEP'})
         & (csv['intake_cond'] != 'DEAD') ),
        # FOSTER
        ['intake_type','intake_date','outcome_type','outcome_date']
        ] . rename(columns=renamedict)
    assert (not (adf['outcome_type'].isna() ^ 
                 adf['outcome_date'].isna()).any())
    return adf

def setFoster (adf):
    adf['fostint'] = adf['intake_type'] == 'FOSTER'
    adf['fostout'] = adf['outcome_type'] == 'FOSTER'
    return adf






