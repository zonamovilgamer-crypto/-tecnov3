from pytrends.request import TrendReq

pytrends = TrendReq(hl='es-AR', tz=360)
trending = pytrends.trending_searches(pn='US')
print(trending.head(10))
