import time
import random

USA_STATES = {
  "AL": ["Birmingham", "Montgomery", "Mobile"],
  "AK": ["Anchorage", "Juneau"],
  "AZ": ["Phoenix", "Tucson", "Mesa"],
  "CA": ["Los Angeles", "San Diego", "San Francisco"],
  "TX": ["Houston", "Dallas", "Austin"],
  "FL": ["Miami", "Tampa", "Orlando"],
  "NY": ["New York City", "Buffalo"]
}

def human_stealth_delay():
    """Randomized delay to prevent rate limiting."""
    time.sleep(random.uniform(2, 5))
