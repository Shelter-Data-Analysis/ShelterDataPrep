#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 28 09:42:32 2024

@author: michaelm
"""
import numpy as np
import pandas as pd

endoftime = pd.to_datetime('2100-01-01')#.date()
categoriesOut = list('RATNIF')

def outcomeFoster (adf):
    adf.loc [adf['fostint'], 'intake']='F'
    adf.loc [adf['fostout'], 'outcome']='F'
    return adf

def standardDate (adf, datedict):
    """ Convert date columns into datetime, 
        keeping only the date portion (remove time) """
    for x,y in datedict.items():
        adf[x] = pd.to_datetime(pd.to_datetime(adf[y]).dt.date)
    return adf

def outcomeConsistency (adf):
    # If there's no outdate but there's an outcome type, assume same day
    nodate = adf['outdate'].isna() & ~adf['outcome'].isna()
    print('nodate', sum(nodate))
    adf.loc[nodate,'outdate'] = adf.loc[nodate,'indate']
    # If there's no outcome type but there's an outdate, discard
    notype = adf['outcome'].isna() & ~adf['outdate'].isna()
    print('notype', sum(notype))
    adf.loc[notype, 'outcome'] = 'X'
    
    # Fill missing Outcome Date with long future date
    inventory = adf['outdate'].isna()
    print ('inventory', sum(inventory))
    adf.loc[inventory,'outdate'] = endoftime
    adf.loc[inventory,'outcome'] = 'I'
    return adf



def getKeyDays (ldf, sampledays):
    startdate = sampledays[0]
    enddate = sampledays[-1]
    mindate = min(ldf.indate.min(), ldf.outdate.min()).date()
    maxdate = max(ldf.indate.max(), ldf.outdate [ldf.outdate!=endoftime].max()).date()
    keydays = (mindate, startdate, enddate, maxdate)
    print ('[mindate, startdate, enddate, maxdate]')
    print (*map(str,keydays))
    assert (mindate < startdate < enddate < maxdate)
    return keydays

def getCumulative (ldf, sampledays):
    cumcols = ['NDays','AnimDays',
               'Incoming','ReTO','Adopt','Transf','Nonlive','CInventEnd']
    outlabels = {'Adopt':'A', 'ReTO':'R', 'Transf':'T', 'Nonlive':'N'}
    # Create a new DataFrame with Mondays as the index
    (mindate, startdate, enddate, maxdate) = getKeyDays (ldf, sampledays)

    cumdf = pd.DataFrame(index=sampledays, columns=cumcols, dtype=int, data=0)
    for day in cumdf.index:
        cumdf.loc[day,'NDays'] = (day - mindate).days + 1
        n = sum(pd.to_timedelta(
            ldf['outdate'].clip (mindate, day) - 
            ldf['indate'].clip (mindate, day) ).dt.days)
        cumdf.loc[day,'AnimDays'] = n
        outs = ldf['outdate'] <= day
        ins = ldf['indate'] <= day
    
        for x,y in outlabels.items():
            cumdf.loc[day,x] = sum(outs & (ldf['outcome']==y) & ~ldf['fostout'])
    
        # Incoming is tracked for RTO fraction: FReTO
        # We cound incoming up to last day, though animal days are only to prior.   
        cumdf.loc [day,'Incoming'] = sum (ins & ~ldf['fostint'])
        cumdf.loc [day,'CInventEnd'] = sum (ins & ~outs)
    return cumdf


