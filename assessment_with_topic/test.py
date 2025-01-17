import time

def my_generator():
    # yield 1
    # time.sleep(2)  # Wait for 1 second before yielding the next value
    return 2

gen = my_generator()
print(gen)

# Iterating over the generator
for value in gen:
    print(value)
