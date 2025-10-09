# This is about testability of fastapi. I want to validate the testing of call with uvicorn.
# create two files
# 1. a simple_api with four calls
#    - a simple public call
#    - an authenticated call with a Authorization Bearer function
#    - raising an Exception leading to a 500 (incl header)
#    - unauthenticatederror as an extenstion to HTTPExtension
# 2. create a xxxx_test file that can be picked up by pytest with test_ functions