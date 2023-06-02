# POP: Prompt Oriented Programming

## Setup

Install from PyPI:

```bash
pip install pop-llm
```

Make sure you have an OpenAI API key in your environment variable: `OPENAI_API_KEY`.

Saving the key to `openai_api_key.txt` is recommended if you are using Jupyter Notebook:

```bash
echo $OPENAI_API_KEY > openai_api_key.txt
```

## Usage

### Getting Started

You can define a "function" using natural language. Simply define a `PopFunction` with three required parameters:

```python
from pop_llm import PopFunction

# Specify the input and output parameters, and a description
add = PopFunction(["a", "b"], ["sum"], "Add the two numbers")
```

Then you can call the function using

```python
answer = add(1, 2)["sum"]
```

If you want to view the raw API response, you can use

```python
raw_answer = add(1, 2)["raw"]
```

Optionally, you can specify these parameters:

```python
add = PopFunction(
    input_keys=["a", "b"], # The names of the input parameters
    output_keys=["sum"], # The names of the output parameters
    description="Add two numbers.", # The description of the task
    name = "add", # A name for the function, default to "function"
    input_assert=lambda a, b: type(a) == int and type(b) == int, # A function to assert the input
    temperature=0 # Set to 0 for deterministic, 1 for the most randomness
)
```

### Allowing LLM to use external tools

You can provide a list of external tools. Simply define some well documented functions and pass them to `PopFunction`.

The LLM Agent will automatically use these tools to help it complete the task.

For example, you have a secret function:

```python
def secret_function(a: int, b: int) -> int:
    """
    A secret function
    Args:
        a: The first number
        b: The second number
    Returns:
        int: The result of the secret function
    """
    return a * 2 + b - 1

secret_function_runner = PopFunction(
    input_keys=["a", "b"],
    output_keys=["output"],
    description="Return the result of the secret function on input a and b.",
    name = "secret_function",
    input_assert=lambda a, b: type(a) == int and type(b) == int,
    temperature=0,
    tools=[secret_function]
)
```

Be creative when defining your tools. This can be a web API, a database call, reading a file, etc.

Note: Your function input should be able to be parsed from JSON. The output should be able to be converted to string without loosing information. (i.e. str(output) is not something like `<object at 0x7f9c2c0b4a90>`)

For more examples, please refer to the [Demo Notebook](./demo.ipynb)
