from vas.utils.geometry import clamp

def test_clamp():
    assert clamp(5,0,10)==5
    assert clamp(-1,0,10)==0
    assert clamp(999,0,10)==10