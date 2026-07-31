#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 28 09:19:05 2024

@author: michaelm
"""

import pandas as pd

name = 'MV'

_ddir = "/Users/michaelm/Library/CloudStorage/OneDrive-Personal/Journal Physics LOS/PRA/"
ddir = _ddir + "Mission Viejo/"
csv_file = ddir+'2016-Feb_2025 Intake Data _Dog-Cat.csv'

sampleStart = pd.to_datetime('2017-01-01').date()
sampleEnd = pd.to_datetime('2024-12-31').date()


datedict = {'indate':'indate', 'outdate':'outdate','dob':'petdob'}
renamedict = {'petsize':'size'}
outcome_type = 'outtype'
intake_type = 'intype'

csv_columns = [
 'impound', 'kennel', 'animalid', 'jurisdiction', 'intype',
 'insubtype', 'indate', 'intime', 'dueout', 'review', 'inby', 'surreason', 'source',
 'total', 'incondition', 'hold',
 'outtype', 'outsubtype', 'outcondition', 'outdate', 'outtime', 'outby', 'outdatenull',
 'petname',
 'animaltype',
 'sex', 'petyears', 'petmonths', 'petdob', 'petage',
 'bites', 'petsize', 'color', 'breed', 'collar']

csv_intake_types = [
    'CONFISCATE',
    'EVACUEE',
    'MUTUAL AID',
    'POLICE IMP',
    'QUARANTINE',
    'RELINQUISH',
    'RESCUE',
    'RETURN',
    'SHELASSIST',
    'STRAY',
    'TRANSFER',
    'VET ASSIST',
    'WELFARE' ]

def getInCodes():
    s = 's' # Stray
    w = 'w' # Owner Surrender
    e = 'e' # Other
    x = 'x' # delete
    d = {'CONFISCATE':e,
        'EVACUEE':e,
        'MUTUAL AID':e,
        'POLICE IMP':e,
        'QUARANTINE':x,
        'RELINQUISH':w,
        'RESCUE':e,
        'RETURN':e,
        'SHELASSIST':e,
        'STRAY':s,
        'TRANSFER':e,
        'VET ASSIST':e,
        'WELFARE':e,
         pd.NA:x}
    return d

csv_outcome_types = [
    'ADOPTION',
    'DIED',
    'EUTH',
    'MUTLAID',
    'OWNER SURR',
    'RESCUE',
    'RTO',
    'TRANS QT',
    'TRANSFER' ]

def getOutCodes():
    R = 'R' # RTO
    A = 'A' # Adoption
    T = 'T' # Transfer
    N = 'N' # Non-LIve 
    I = 'I' # Inventory (still in shelter)
    F = 'F' # Foster
    X = 'X' # to be crossed out
    d = {'ADOPTION':A,
        'DIED':N,
        'EUTH':N,
        'MUTLAID':X,
        'OWNER SURR':X,
        'RESCUE':T,
        'RTO':R,
        'TRANS QT':X,
        'TRANSFER':T }
    return d

def sizeTrans (s):
    if isinstance(s,str):
        s = s[0]
        if s in 'XLMSTP':
            return s
    return 'M'

def filterRawData (csv):
    adf = csv.loc[
        (csv['animaltype']=='DOG') & 
        (csv['outtype'].isna() == csv['outdate'].isna())
        ,        
        ['intype','indate','outtype','outdate','petsize','petdob']
        ] . rename(columns=renamedict)
    adf['size'] = adf['size'].map(sizeTrans)
    assert True
    return adf

def setFoster (adf):
    adf['fostint'] = False 
    adf['fostout'] = False
    return adf






