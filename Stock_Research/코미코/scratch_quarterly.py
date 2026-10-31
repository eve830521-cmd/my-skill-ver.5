import FinanceDataReader as fdr
import pandas as pd

df = fdr.DataReader('183300', '2017-01-01')
q = df.resample('QE').agg({'Close': 'last', 'Volume': 'sum', 'High': 'max', 'Low': 'min'})
for idx, row in q.iterrows():
    period = f"{idx.year}-Q{(idx.month-1)//3 + 1}"
    print(f"{period}: Close={row['Close']:>6.0f}, Low={row['Low']:>6.0f}, High={row['High']:>6.0f}, Vol={row['Volume']:>10.0f}")
