# ServantPhone
Ai voice agent with a voip softphone interface to enable a natural interaction between users and [servant](https://github.com/ucpdh23/servant).

The main interface of Servant is Telegram. Servant is executed as a bot where the users can execute and interacts with the available actions and events.
However, this interface is not enough if you are searching for a more natural and intuitive interaction with this system. In order to move forward on this, a new "telephone" command has been included in Servant. This command executes this new piece of software as an external procedure; starting a phone call between the end user and an AI ReAct agent empowered with some MCP tools provided by Servant. Then, the use can ask this agent to perform any operation in Servant, or even more! With additional MCP tools this agent can be used to perform more advances operations.


Current Business Use Cases:
- Every day I have to drive from my home to the office. During this time I can check my personal agenda, update my shopping list or just discuss with the AI about any topic. I can also ask the AI to send to me an IM with a summary in Telegram.
- During summer time, we use to drive a lot to travel from one city to the next one. As we travel with two kids, we need to spend as much time as possible with games. For this reason, playing with the AI to discover the city based on clues provided by the IA is our new hobby.



# How to build and execute

First of all, you need to build [pjsua2](https://docs.pjsip.org/en/latest/pjsua2/intro.html). This module provides a ready-to-use implementation of SIP in order to simplify and develop the VoIP component of this project. See the [build](https://docs.pjsip.org/en/latest/pjsua2/building.html) page to install this dependency in your system. 


## SIP Integration
SIP protocol in general, and PJSUA2 module in particular, both include a vast number of options and variables to setup the account and the call for audio playback and capturing. The specific implementation in this project is based on the analysis, experimentation and testing performed until the system has been able to be executed automatically and without human supervision in my environment and context.
For analysis and troubleshooting purposes, apart from [PJSUA2 basecode](https://github.com/pjsip/pjproject) analysis and review, these three tools has been used: [MicroSIP](https://www.microsip.org/), [Wireshark](https://www.wireshark.org/) and Linux TCPDump.


# How this module works

This module initiates the phone call to the requested phone number (SIP-VoIP). Then, every 0.5 seconds a new audio segment is generated. This segment is analyzed in order to identify a speech from the user to determine how to process it.
With the speech from the user, a GenIA Module is called to extract the text (STT), process it with an LLM Agent, and finally transcript the output into an audio.
In audio is queued into a playback queue. Then, this queue is processed and played to the user using the SIP-VoIP output channel. 


# GenAI Agent details

Using Langchain ReAct Agent with the Servant MCP Toolkit to interact with Servant. The MCP toolkit enables some features from Servant such as updating and reading the shopping list, reading the calendar, building a message to be shared with the user through Telegram, and others. Please see [Servant](https://github.com/ucpdh23/Servant) documentation for further details about other capabilities.

## MCP Toolkit

This Agent uses some MCP Tooks provided by Servant. Servant implements a MCP Server and provides some asynchronous tools. These tools invoke actions based on the Actions and Events design of Servant.
The MCP server has been implemented using the [MCP Java SDK framework](https://github.com/modelcontextprotocol/java-sdk). However, this implementation has been adapted to be embedded into Vertx. Please note that this enhancement has been performed as a POC and the protocol has not been fully implemented and tested.

