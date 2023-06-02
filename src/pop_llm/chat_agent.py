import openai
import tiktoken
import logging
import json
import os
from typing import List
from datetime import datetime
from typing import Union, Callable
from .prompts import TOOL_PROMPT_PREFIX, TOOL_PROMPT_SUFFIX, INDENT


class OpenAIMessage(dict):
    """
    Class representing a message. A message includes role and content.
    """

    def __init__(self, role: str, content: str) -> None:
        """
        Initialize a Message instance

        Args:
            role (str): Role the message is from, can be 'user' or 'system'.
            content (str): Content of the message.
        """
        super().__init__()
        self.__dict__ = self
        self.role = role
        self.content = content


class OpenAIAgent:
    """
    An OpenAI chat agent that uses the OpenAI API to generate responses
    """

    def __init__(
        self,
        system_prompt: str = "",
        history: List[OpenAIMessage] = [],
        max_tokens: int = 4096,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.5,
        output_keys: List[str] = [],
        tools: List[Callable] = [],
    ) -> None:
        """
        Initialize the chatbot

        Args:
            system_prompt (str, optional): A system prompt. Defaults to "".
            history (List[Message], optional): The conversation history. Defaults to [].
            max_tokens (int, optional): The maximum token size. Defaults to 4096.
            model (str, optional): The OpenAI model to use. Defaults to "gpt-3.5-turbo".
            temperature (float, optional): The randomness of the response generation. Defaults to 0.9.
            output_keys (List[str], optional): The keys of the output if you want JSON formatted output. Defaults to [].
            tools (List[Callable], optional): A list of tools that can be used by the chatbot. Defaults to [].
        """
        self.output_keys = output_keys
        self.tools = tools
        if "tool" in output_keys or "args" in output_keys:
            raise ValueError("'tool' and 'args' are reserved output keys.")
        # Generate tool prompt
        self.system_prompt = system_prompt

        if len(self.tools):
            self.output_keys.extend(["tool", "args"])
            self.system_prompt += "\n"
            self.system_prompt += generate_tools_prompt(self.tools)

        self.history = history
        self.max_tokens = max_tokens
        self.model = model
        self.temperature = temperature
        if not len(self.history):
            self.history.append(OpenAIMessage("system", self.system_prompt))
        self.tools = tools
        # Validate tools
        for tool in self.tools:
            if not callable(tool):
                raise ValueError("All tools must be callable.")
            if not tool.__doc__:
                raise ValueError("All tools must have a docstring.")

    def add_message(self, message: OpenAIMessage) -> None:
        """
        Add a new message to the chatbot's history

        Args:
            message (Message): The message to add.
        """
        self.history.append(message)

    def send_history(self) -> OpenAIMessage:
        """
        Send the chatbot's history to OpenAI API and receive the response

        Returns:
            Message: The response message from the API.
        """
        try:
            completion = openai.ChatCompletion.create(
                model=self.model,
                messages=self.history,
                temperature=self.temperature,
            )
            response_message = OpenAIMessage(
                completion["choices"][0]["message"]["role"],
                completion["choices"][0]["message"]["content"],
            )
        except openai.error.RateLimitError as e:
            logging.error(str(e))
            logging.info("Retrying...")
            return self.send_history(self.history)
        self.history.append(response_message)
        return response_message

    def summarize_history(self, keep_recent: int = 2) -> None:
        """
        Summarize the chatbot's history using the OpenAI API

        Args:
            keep_recent (int, optional): The number of recent messages to keep. Defaults to 2.
        """
        logging.info("Summarizing the chatbot's history...")
        prompt = "Summarize the conversation so far in less than 100 words\n"
        self.add_message(OpenAIMessage("user", prompt))
        summary = self.send_history().content
        summary = "This is a summary of the conversation so far\n" + summary
        summary_message = OpenAIMessage("system", summary)
        self.history = self.history[1 : len(self.history) - keep_recent]
        self.history.insert(1, summary_message)
        logging.info("Chatbot history summarized. Summary: %s", summary)

    def pop_oldest_history(self) -> None:
        """
        Pop the oldest message from the chatbot's history
        """
        # Keep the first system message
        if len(self.history) > 2:
            self.history.pop(1)
        else:
            logging.error("Cannot pop oldest history. History is empty.")
            raise ValueError("Cannot pop oldest history. History is empty.")

    def reset_history(self) -> None:
        """
        Reset the chatbot's history to the first system message
        """
        self.history = [self.history[0]]

    def check_token_usage(self) -> float:
        """
        Check the token usage of the chatbot's history

        Returns:
            float: The token usage as a fraction of the maximum tokens.
        """
        contents = "\n".join([m["content"] for m in self.history])
        enc = tiktoken.encoding_for_model(self.model)
        token_usage = len(enc.encode(contents)) / self.max_tokens
        logging.debug("Token usage: %.2f", token_usage)
        return token_usage

    def run(self, prompt: str, role: str = "user") -> str:
        """
        Run the chatbot with a given prompt

        Args:
            prompt (str): The prompt to initiate or continue the conversation.

        Returns:
            str: The response content from the chatbot.
        """
        prompt_of_time = f"current datetime: {datetime.now()}, today is {datetime.now().strftime('%A')}\n"
        if len(self.output_keys):
            output_key_str = str(self.output_keys).replace("'", '"')
            prompt_of_output_format = f"Your output should be a JSON string with the following keys: {output_key_str}\n"
        prompt = "Input: " + prompt
        logging.debug(
            "Running chatbot with prompt: %s",
            prompt_of_time + prompt_of_output_format + prompt,
        )
        self.add_message(
            OpenAIMessage(role, prompt_of_time + prompt_of_output_format + prompt)
        )
        # Check token usage before sending history
        while self.check_token_usage() >= 1:
            # self.summarize_history()
            # TODO: summarize history
            try:
                self.pop_oldest_history()
            except ValueError:
                raise ValueError("Token usage exceeded maximum tokens.")
        response = self.send_history()
        # Parse output if output keys are specified
        parsed_content = self.parse_output(response.content)

        # Call the tool if the output contains a tool name
        args = None
        if (parsed_content.get("tool", None) not in {None, ""}):
            args = parsed_content.get("args", None)
            tool_output = self.use_tool(parsed_content["tool"], args)
            tool_output = f"Tool output: {tool_output}\n"
            tool_output += (
                "\n Observe the output and continue the conversation."
                + "\n Do not use the tool if you are ready to complete the task."
            )
            # Run with the tool output as the prompt
            return self.run(tool_output, "system")
        return parsed_content

    def rerun(self, prompt: str) -> str:
        """
        Remove all messages after the last user message and run the chatbot with a given prompt

        Args:
            prompt (str): The prompt to initiate or continue the conversation.
        """
        # Get the index of the last user message
        last_user_message_index = -1
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i].role == "user":
                last_user_message_index = i
                break
        if last_user_message_index == -1:
            raise ValueError("No user message found in history")
        # Remove all messages after the last user message
        self.history = self.history[: last_user_message_index + 1]
        return self.run(prompt)

    def parse_output(self, output: str) -> Union[str, dict]:
        """
        Parse the output of the chatbot if the output keys are specified. Call the tool if the output contains a tool name.

        Args:
            output (str): The output of the chatbot.

        Returns:
            Union[str, dict]: The parsed output.
        """
        if not len(self.output_keys):
            return output
        logging.debug("Parsing output: %s", output)
        parsed_output = {}
        parsed_output["raw"] = output
        # Select the text between the first and last curly braces
        try:
            # Get the text between the first and last curly braces
            output = output[output.index("{") : output.rindex("}") + 1]
            output_dict = json.loads(output)
        except json.decoder.JSONDecodeError as e:
            logging.error(str(e))
            # Provide the exception to chatbot
            output = self.run(
                "There was an error parsing your response: "
                + str(e)
                + "\nTry to fix your response format and run again.\n",
                "system",
            )
            # Try parsing again
            # TODO: Add a limit to the number of times the chatbot can try parsing to prevent infinite loops
            if type(output) == dict:
                return self.parse_output(output["raw"])
            else:
                return self.parse_output(output)
        except ValueError as e:
            return parsed_output
        for key in self.output_keys:
            parsed_output[key] = output_dict.get(key, None)
        return parsed_output

    def use_tool(self, tool_name: str, args: list) -> str:
        """
        Use a tool with the chatbot

        Args:
            tool (str): The name of the tool to use.
            args (List[str]): The arguments to pass to the tool.

        Returns:
            str: The output of the tool.
        """
        print(f'Using tool: "{tool_name}" with args: {args}')
        # input("Press Enter to continue...")
        logging.info("Using tool %s with args %s", tool_name, args)
        # Find the tool
        tool = None
        for t in self.tools:
            if t.__name__ == tool_name:
                tool = t
                break
        if tool is None:
            return f"Tool {tool_name} not found. Please try a valid tool."
        # Get args
        try:
            if args is None or len(args) == 0:
                return tool()
            else:
                return tool(*args)
        except Exception as e:
            return f"Error using tool {tool_name}: {str(e)}"

    def save_history(self, path: str = "./history.json") -> None:
        """
        Save the chatbot's history to a file

        Args:
            path (str): The path to save the history to.
        """
        # if path is a directory, save to a file in the directory
        if os.path.isdir(path):
            path = os.path.join(path, "history.json")
        with open(path, "w") as f:
            json.dump([m for m in self.history], f, indent=4)
        logging.info("Chatbot history saved to %s", path)

    def load_history(self, path: str = "./history.json") -> None:
        """
        Load the chatbot's history from a file

        Args:
            path (str): The path to load the history from.
        """
        try:
            with open(path, "r") as f:
                history = json.load(f)
                self.history = [OpenAIMessage(m["role"], m["content"]) for m in history]
        except FileNotFoundError as e:
            logging.error(str(e))
            return
        logging.info("Chatbot history loaded from %s", path)


def generate_tools_prompt(tools) -> str:
    """
    Generate the prompt for the tools
    """
    if not len(tools):
        return ""
    prompt = TOOL_PROMPT_PREFIX
    for tool in tools:
        prompt += f"Name: {tool.__name__}\n"
        prompt += f"Description: {tool.__doc__}\n\n"
    prompt += TOOL_PROMPT_SUFFIX
    return prompt
