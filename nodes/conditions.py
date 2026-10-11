"""Tool-routing conditions used by graph.py."""
from langchain_core.messages import AIMessage
from state import State
import config


def tool_or_answer(state: State) -> str:
    """Execute every emitted call; enforce the decision limit after its result."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "answer"


def after_tools(state: State) -> str:
    """After tools: loop back to llm_tool while under the iteration limit
    (enables multi-step tool chaining), otherwise go to answer."""
    if state.get("iteration_count", 0) < config.MAX_ITERATIONS:
        return "llm_tool"
    return "answer"
