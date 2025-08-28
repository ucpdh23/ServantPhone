# ServantPhone
Ai voice agent with a voip softphone interface to enable a natural interaction between users and [servant](https://github.com/ucpdh23/servant).

The main interface of Servant is Telegram. Servant is executed as a bot where the users can execute and interacts with the available actions and events.
However, this interface is not enough if you are searching for a more natural and intuitive interaction with this system. In order to move forward in this, a new "telephone" command has been included in Servant. This command executes this new piece of software as an external procedure; starting a phone call with an AI ReAct agent empowered with some MCP tools provided by Servant.

Business Use Cases:
- Every day I have to drive from my home to the office. During this time I can check my personal agenda, update my shopping list or just discuss with the AI about any topic. I can also ask the AI to send to me an IM with a summary in Telegram.
- During summer time, we use to drive a lot from one location to the next one. As we travel with two children, we need as much games as possible. playing with the AI to discover the city is our new hobby. 

# How to build and execute

First of all, you need to build [pjsua2](https://docs.pjsip.org/en/latest/pjsua2/intro.html). This module provides a ready-to-use implementation of SIP in order to simplify and develop the VoIP component of this project. See the [build](https://docs.pjsip.org/en/latest/pjsua2/building.html) page to install this dependency in your system. 

