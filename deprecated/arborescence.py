# In here I try to create a thought arborescence with AI

from ai_core import AI
from lxml import etree
from typing import List

PROMPT_MASTER = """
You are an expert with LLMs and a prompt engineer.
You are given the following task:

<task_description>
{task}
</task_description>

You must decide whether 
    a. you should send this task to a single, state of the art LLM (using your excellent prompt engineering skill), or 
    b. instead send it to another LLM that will break it down into more manageable subtasks.
Write down your reflexions inside the <reflexions> tag, and your decision under the <decision> tag. Use exactly the word "direct" for decision a and "subtasks" for decision b.

Example:
<reflexions>
This task seems very simple, and this is a domain where LLMs are very competent, so I am confident that sending it to a single LLM with a good prompt will be enough.
</reflexions>
<decision>
direct
</decision>
"""

PROMPT_MASTER_DIRECT = """
Excellent. Please craft a prompt that will ensure that this task likely to be completed to a high degree of satisfaction.
Write down your reflexions inside the <reflexions> tag, and your prompt under the <prompt> tag.
"""

PROMPT_SUBTASKER = """
You are a professional prompt engineer.
Please read the task below carefully. Your goal is to break it down into subtasks.
Each subtask will be fed to a different LLM. Make sure to write it down as a prompt destined to a state of the art LLM.

<task>
{task}
</task>

Here are a few of my reflexions on the decision to break it down into subtasks.
<my_reflexions>
{reflexions}
</my_reflexions>

Write down your own reflections first inside the <reflexions> tag.
Then write down each of the subtasks into separate <subtask> tags. Remember that these are prompts for LLMs.
Each subtask will be executed in order and will get access to the output from all the previous subtasks.

Example of output structure:
<reflexion>
your reflexions before breaking down the task
</reflexions>
<subtask>
The prompt of the first subtask
</subtask>
<subtask>
The prompt of the second subtask
</subtask>
...
"""

PROMPT_SUBTASKER_FINAL = """
You will find below the answers to all the subtasks you decided to solve.

{tasks_outputs}

Using this information, please write an answer to the original task.
Write down your answer inside the <output> tags like so:
<output>
Your answer to the original task
</output>
"""

PROMPT_IN_CONTEXT = """
You are an expert prompt engineer.
You are given the following prompt
<prompt>
{prompt}
</prompt>
Your role is to rewrite it with the appropriate context from all these other tasks that have been completed before this one:
{tasks_outputs}

Note that it is possible that this prompt was self contained and did not need any context from the previous tasks. If that is the case, feel free to return an exact copy.
Whatever you decide, remember that the prompt you provide needs to be standalone. You cannot make references to anything outside of it so make sure to include all the necessary key takeaways from the previous tasks and answers.

Write down your new prompt inside <prompt> tags like so:
<prompt>
Your new prompt, that adds the necessary context from the previous tasks.
</prompt>
"""
TASK_OUTPUT = """<task>{task}</task>
<output>{output}</output>
"""

TASK_TEST_1 = "Write me a haiku about the history of the world"
TASK_TEST_2 = "Write a 4 pages opinionated essay about the nature of consciousness"
TASK_TEST_3 = "Write me a haiku about pizza"

master = AI("opus")
subtasker = AI("opus")
context = AI("opus")
actor = AI("opus")

def extract_text_under_tag(xml: str, tag: str) -> str:
    extracted = etree.fromstring(xml).find(tag)
    assert extracted is not None, f"Can't find tag {tag} in xml {xml}"
    text = extracted.text.strip()
    assert text, f"Empty text for xml: {xml}, tag: {tag}"
    return text

def extract_text_under_tags(xml: str, tag: str) -> List[str]:
    extracted = etree.fromstring(xml).findall(tag)
    assert len(extracted), f"No tag {tag} in xml {xml}"
    texts = []
    for el in extracted:
        text = el.text.strip()
        assert text, f"Empty text in one of tags {tag} in xml: {xml}"
        texts.append(text)
    return texts

if __name__ == "__main__":
    task = TASK_TEST_1
    print(task)
    xml_response = master.conversation(
        PROMPT_MASTER.format(task=task), xml=True)
    print(xml_response)

    reflexions = extract_text_under_tag(xml_response, "reflexions")

    decision = extract_text_under_tag(xml_response, "decision")
    assert decision == "direct" or decision == "subtasks"

    if decision == "subtasks":
        xml_response = subtasker.conversation(
            PROMPT_SUBTASKER.format(
                reflexions=reflexions,
                task = task
                ), xml=True)
        print(xml_response)

        subtasks = extract_text_under_tags(xml_response, "subtask")
        answers = []
        for subtask in subtasks:
            if len(answers) > 0:
                tasks_outputs = ""
                for i, answer in enumerate(answers):
                    tasks_outputs += TASK_OUTPUT.format(
                        task = subtask[i], output = answer)
                xml_response = context.message(
                    PROMPT_IN_CONTEXT.format(
                        prompt=subtask,
                        tasks_outputs = tasks_outputs
                    ), xml=True)

                subtask_in_context = extract_text_under_tag(xml_response, "prompt")
            else:
                subtask_in_context = subtask
            print("SUBTASK IN CONTEXT")
            print(subtask_in_context)
            xml_response = context.message(
                subtask_in_context, xml=True
            ).content
            answer = actor.message(subtask_in_context).content
            print("ANSWER")
            print(answer)
            answers.append(answer)

        for subtask, answer in zip(subtasks, answers):
            tasks_outputs += TASK_OUTPUT.format(
                task = subtask[i], output = answer)
            xml_response = subtasker.conversation(
                PROMPT_SUBTASKER_FINAL.format(tasks_outputs = tasks_outputs),
                xml=True
                )
            final_response = extract_text_under_tag(xml_response, "output")
            print()
            print("FINAL RESPONSE")
            print(final_response)

    elif decision == "direct":
        response = master.conversation(PROMPT_MASTER_DIRECT)
        print(response)
        xml_response = f"<response>{response}</response>"

        prompt = etree.fromstring(xml_response).find("prompt")
        assert prompt is not None
        prompt = prompt.text.strip()
        assert prompt

        response = actor.message(prompt).content
        print("-----")
        print("FINAL RESPONSE: ")
        print(response)


    # print("----")
    # print(TASK_TEST_2)
    # response = claude.message(PROMPT_MASTER.format(task=TASK_TEST_2))
    # print(response)

