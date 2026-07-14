from slowapi import Limiter
from slowapi.util import get_remote_address

# In-memory, per-process limiter — enough for abuse protection on the auth
# endpoints at this scale.
limiter = Limiter(key_func=get_remote_address)
