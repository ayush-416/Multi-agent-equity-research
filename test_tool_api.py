from langchain.tools import tool

@tool
def test_tool(x: str) -> str:
    """Test tool for checking API."""
    return x

print('Direct call:', hasattr(test_tool, '__call__'))
print('Has .func:', hasattr(test_tool, 'func'))
print('Has .invoke:', hasattr(test_tool, 'invoke'))
print('Type:', type(test_tool))

# Try different call methods
try:
    result1 = test_tool.func("test1")
    print('.func() works:', result1)
except Exception as e:
    print('.func() error:', e)

try:
    result2 = test_tool.invoke({"x": "test2"})
    print('.invoke() works:', result2)
except Exception as e:
    print('.invoke() error:', e)

try:
    result3 = test_tool("test3")
    print('Direct call works:', result3)
except Exception as e:
    print('Direct call error:', type(e).__name__, str(e))

