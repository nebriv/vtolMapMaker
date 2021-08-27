#!/bin/bash
echo "Inflating GHS Data"
gunzip "GHS_Data.npy.gz"
python wsgi.py