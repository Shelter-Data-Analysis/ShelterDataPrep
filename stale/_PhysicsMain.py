#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 17 14:35:08 2024

@author: michaelm
"""
import numpy as np
import pandas as pd
import os
wdir = _ddir = "/Users/michaelm/Desktop/GitProjects/ShelterDataPrep/stale/"
os.chdir(wdir)
from _PhysicsSubs import *


import orangecounty as shelter

GENERATE_CSV = False

#################### csv #################################################

# Read the CSV file into a DataFrame called csv, creating a new index.  
csv = pd.read_csv (shelter.csv_file, index_col=False)
print(shelter.name)
#################### adf, ldf ########################################
# copy out live dog intakes and useful columns
adf = shelter.filterRawData(csv).copy(deep=True)

# Compute date columns
standardDate (adf, shelter.datedict)
    
# Convert Outcome Types to our standard codes
outdict = shelter.getOutCodes ()
adf['outcome'] = adf [shelter.outcome_type] .map (outdict)
outcomeConsistency (adf)

# Remove all discards
adf = adf[adf['outcome'] != 'X']
# convert outcome to category
adf['outcome'] = pd.Categorical (
    adf['outcome'], categories = categoriesOut, ordered=True)

shelter.setFoster (adf)
# print(adf.head(3).T, '\n', print(adf.tail(3).T)
# adf.to_csv (shelter.ddir+'adf.csv')

ldf = adf[['indate','outdate','outcome', 'fostint', 'fostout']].copy(deep=True)
print(shelter.name)
if GENERATE_CSV: ldf.to_csv (shelter.ddir+'ldf.csv')
#################### cumdf #################################################
# Create a date range of Mondays
sampledays = pd.date_range(start=shelter.sampleStart, 
                           end=shelter.sampleEnd, freq='W-MON').date
keydays = getKeyDays (ldf, sampledays)
cumdf = getCumulative (ldf, sampledays)

print(shelter.name)
if GENERATE_CSV: cumdf.to_csv(shelter.ddir+'cumdf.csv')
#################### subdf, qdf #############################################

weeks = 17
sweeks = str(weeks).zfill(2)
print(shelter.name, sweeks)


shiftdf = cumdf.shift(weeks)
qdf = (cumdf - shiftdf)[weeks:]
qdf['CInventEnd'] = cumdf['CInventEnd']

qdf['CInventAvg'] = qdf['AnimDays'] / qdf['NDays']
qdf['DIntake'] = qdf['Incoming'] / qdf['NDays']
qdf['FReTO'] = qdf['ReTO'] / qdf['Incoming']
qdf['PAdopt'] = qdf['Adopt'] / qdf ['AnimDays']
qdf['PTransf'] = qdf['Transf'] / qdf ['AnimDays']
qdf['PNonlive'] = qdf['Nonlive'] / qdf ['AnimDays']

qdf['PP'] = qdf['PAdopt'] + qdf['PTransf'] + qdf['PNonlive']
qdf['PRTO'] = qdf['FReTO'] * qdf['DIntake'] / qdf['CInventAvg']
qdf['PAggreg'] = qdf['PP'] + qdf['PRTO']

qdf['CInventEquil'] = qdf['DIntake']*(1-qdf['FReTO']) / qdf['PP']

qdf['LAggreg'] = 1 / qdf['PAggreg']
qdf['LEquil'] = qdf['CInventEquil'] / qdf['DIntake']

qdf['SaveR'] = 1 - qdf['PNonlive'] * qdf ['LAggreg']
qdf['Nosa'] = 1 - qdf['SaveR']
qdf['SaveEquil'] = 1 - qdf['PNonlive'] * qdf ['LEquil']
qdf['NosaEquil'] = 1 - qdf['SaveEquil']

print(shelter.name)
if GENERATE_CSV: qdf.to_csv (shelter.ddir+'qdf'+sweeks+'.csv')


# subdf.to_csv (ddir+'subdf.csv')
# qdf.to_csv (ddir+'qdf.csv')
