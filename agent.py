import asyncio
from typing import List, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool, BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI 
from langchain_core.prompts import MessagesPlaceholder
from langgraph.checkpoint.memory import InMemorySaver

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_PROMPT = os.getenv('LLM_PROMPT')
MCP_URL = os.getenv('MCP_URL')

class MCPAgent:
    """
    Agent to process the user input (as a text from the audio).
    This agent can use various tools and APIs to fulfill the user's request.
    Finally, this agent generates a response (to then be sent back to the user as audio).
    """

    def __init__(self):
        self.checkpointer = InMemorySaver()

    async def _ainitialize(self, role: str):
        self.tools = await self._load_mcp_tools() 
        print(self.tools)

        self.llm = ChatOpenAI(model="gpt-4o", api_key=LLM_API_KEY, temperature=0)

        self.agent_executor: Runnable = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.checkpointer, 
            prompt=role 
        )
        print("Agent created")

    async def _load_mcp_tools(self) -> List[BaseTool]:
        client = MultiServerMCPClient(
            {
                "servant": {
                    "url": MCP_URL,
                    "transport": "sse",
                }
            }
        )
        return await client.get_tools()


    async def execute(self, message: str) -> str:
        print(f"\n--- Running with input: '{message}' ---")
        
        inputs = {"input": message}
        try:
            config = {"configurable": {"thread_id": "1"}}
            result = await self.agent_executor.ainvoke({"messages": [{"role": "user", "content": message}]}, config)
            print(result['messages'][-1].content)
            final_message = result['messages'][-1].content

            if final_message:
                return final_message
            else:
                return "I cannot get a clear answer from the agent."
        except Exception as e:
            print(f"Error in agent: {e}")
            return f"Lo siento, hubo un error al procesar tu solicitud: {e}"


async def main():
    print("Creating agent instance...")
    agent = MCPAgent()

    role = LLM_PROMPT
    await agent._ainitialize(role=role)
    
    print("MCPAgent instanciated.")

    # Prueba 1: Pregunta que debería activar tool
    user_message_1 = "Me puedes decir la temperatura exterior de la casa?"
    response_1 = await agent.execute(user_message_1)
    print(f"\nUsuario: {user_message_1}")
    print(f"Agente: {response_1}")



# Bloque para ejecutar como script
if __name__ == "__main__":
    asyncio.run(main())

