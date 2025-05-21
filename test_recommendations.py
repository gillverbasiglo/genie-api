import asyncio
import sys

from app.services.recommendation_service import (
    stream_genie_recommendations
)

async def test_streaming_recommendations(ip_address: str):
    """Test the streaming version of recommendations."""
    print("Testing streaming recommendations...")
    print("=" * 50)
    try:
        async for recommendation in stream_genie_recommendations(ip_address):
            print("\nReceived recommendation:")
            print("-" * 30)
            print(recommendation)
            print("-" * 30)
    except Exception as e:
        print(f"Error in streaming recommendations: {e}")


async def main():
    # You can replace this with any IP address you want to test
    test_ip = "8.8.8.8"  # Google's public DNS IP as an example
    
    # If an IP is provided as command line argument, use it
    if len(sys.argv) > 1:
        test_ip = sys.argv[1]
    
    print(f"Testing with IP address: {test_ip}")
    
    # Test both versions
    await test_streaming_recommendations(test_ip)

if __name__ == "__main__":
    asyncio.run(main())