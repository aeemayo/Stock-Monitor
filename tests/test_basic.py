from roma.agents import PriceAgent

def test_price_fetch():
    pa = PriceAgent()
    df = pa.fetch('AAPL', period='5d')
    assert df is not None
    assert 'y' in df.columns
