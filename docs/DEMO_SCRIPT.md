# OffPeak demo script (aim for 2:30–2:45, must be under 3:00)

**Setup:** quiet room, laptop speakers on (no headphones), volume up. Cmd+Shift+5 → Record Selected Portion → Options → Microphone: MacBook Microphone.
**Before each clip:** click **Start over** on the page.
**Record one clip per scene.** Re-do any that go wrong. Join them in iMovie.

---

### 1. Hook (0:00–0:20)
*Screen at rest. Don't click anything.*

> "Around Chicago, more than 70,000 homes pay for electricity by the hour, and about 22,000 of them have an EV. The price changes all day. It can spike in the evening, and sometimes it even goes below zero. Nobody's going to watch that. So I built OffPeak, a home energy autopilot for Alexa+."

### 2. Price right now (0:20–0:40)
*Tap the mic and say:* **"What's power costing right now?"**
*Let it answer.*

> "That's the live price from ComEd, the same rate these homes actually pay."

*If it's below zero:* "And right now it's actually negative. People on this plan are getting paid to use power."

### 3. Autopilot (0:40–1:10)
*Say:* **"Autopilot tonight."**
*Wait for the answer. The icons pop up on the price bar.*

> "It just planned my night. The car charges in the cheapest hours and is ready by morning, and the dishwasher and dryer move off the expensive hours. Each one is pinned to when it'll run, and it tells me what I saved."

### 4. Memory and rules (1:10–1:30)
*Say:* **"I need the car by 6 tomorrow, and charge it to 90 percent."**

> "It saves that and re-plans. It remembers my rules next time too, and it won't break them."

### 5. The price spike (1:30–2:10). The big moment.
*Click* **Play a price spike**.

> "Now I'm replaying an evening price spike. My car just plugged in and the dryer's running."

*Stop talking and wait. The screen turns red and OffPeak speaks on its own. Let it finish.*

> "I didn't ask it anything. It noticed the spike, paused the car and moved charging so it's still ready in the morning, held the dryer, turned the heat down a little within my limits, and told me what it saved."

*Optional: open "Show what OffPeak did" under the screen for two seconds.*

### 6. How it works (2:10–2:40)
*Switch to github.com/mandoskann/offpeak and scroll to the diagram.*

> "Under the hood there's an MCP server with ten tools running on live ComEd prices. An Agent Skill tells OffPeak how to talk and what to do, and Claude runs the agent through the Strands Agents SDK. A watcher checks prices on its own, which is why it can act without being asked. The devices are simulated for now, but they're plugged in through one spot, so real thermostats and EV chargers are next."

> "That's OffPeak. Your home, using power at the right time."

---

### If something goes wrong
- **Slow or weird answer:** stop and re-record that clip.
- **Mic doesn't hear you:** type the question instead. It works the same.
- **Running long:** cut scene 4 first.
