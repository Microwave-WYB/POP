import logging
import json
from typing import Any, List, Callable
from .chat_agent import OpenAIAgent
from .prompts import POP_PROMPT_PREFIX

INDENT = "    "


class PopFunction:
    """
    A class for Prompt Oriented Programming (POP) functions.
    """

    def __init__(
        self,
        input_keys: List[str],
        output_keys: List[str],
        description: str,
        name: str = "function",
        input_assert: Callable[[Any], bool] = None,
        temperature: float = 0.0,
        tools: List[Callable] = [],
        agent: OpenAIAgent = None,
    ) -> None:
        """
        Initialize a POP function.

        Args:
            input_keys (List[str]): The input keys of the function.
            output_keys (List[str]): The output keys of the function.
            description (str): The description of the function.
            name (str, optional): The name of the function. Defaults to "function".
            input_assert (Callable[[Any], bool], optional): The assertion function for the input. Defaults to None.
            temperature (float, optional): The temperature of the chatbot. Defaults to 0.0.
            tools (List[Callable], optional): The tools of the chatbot. Defaults to None.
            agent (OpenAIAgent, optional): The agent of the chatbot. Defaults to a default OpenAIAgent instance.
        """
        self.input_keys = input_keys
        self.name = name
        self.description = description
        self.output_keys = output_keys
        self.system_prompt = POP_PROMPT_PREFIX
        self.system_prompt += f"Your name is: {self.name}.\n"
        self.system_prompt += f"Your task is described as follows:\n"
        self.system_prompt += f"{INDENT}{description}\n"
        self.system_prompt += f"Your input keys are: \n"
        self.system_prompt += json.dumps(self.input_keys) + "\n"
        self.system_prompt += f"Your output keys are: \n"
        self.system_prompt += json.dumps(self.output_keys) + "\n"

        self.agent = agent if agent else OpenAIAgent(
            system_prompt=self.system_prompt,
            output_keys=output_keys,
            temperature=temperature,
            history=[],
            tools=tools,
        )

        self.input_assert = input_assert

        doc = f"Description: {self.description}\n"
        doc += "\nArgs:\n"
        for key in self.input_keys:
            doc += f"{INDENT}{key}: function input.\n"
        doc += "\nReturns:\n"
        for key in self.output_keys:
            doc += f"{INDENT}{key}: function output.\n"
        self.__doc__ = doc

    def __call__(self, *args: Any, **kwds: Any) -> dict:
        """
        Run the function by sending input to the chatbot.

        Returns:
            dict: The output of the function.
        """
        logging.info(f"Calling function {self.name} with args {args} and kwds {kwds}")
        if self.input_assert is not None:
            assert self.input_assert(*args, **kwds), "Input does not satisfy assertion."
        input_dict = dict(zip(self.input_keys, args))
        input_dict.update(kwds)
        input_dict_str = str(input_dict).replace("'", '"')
        output_dict = self.agent.run(input_dict_str)
        # raise error if output_dict does not contain all output_keys
        for key in self.output_keys:
            if key not in output_dict:
                logging.warning(
                    f"Output key '{key}' is not found in the output dictionary."
                )
                self.agent.run(
                    f"Make sure you have all the required output keys: {self.output_keys}."
                )
        return output_dict


if __name__ == "__main__":
    add = PopFunction(
        input_keys=["a", "b"],
        output_keys=["sum"],
        description="Add two numbers.",
        name="add",
        input_assert=lambda a, b: isinstance(a, int) and isinstance(b, int),
    )

    print(add(1, 2))
