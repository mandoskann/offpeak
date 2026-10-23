# OffPeak: demo video script (target 2:40, hard limit under 3:00)

**Rules:** no Alexa logo, no copyrighted music, English. Upload to YouTube as public or unlisted.
**Record with:** QuickTime → File → New Screen Recording, with your mic on. Record the Chrome window at http://127.0.0.1:8080.
**Before each take:** click **Reset**, then wait for the price chip to show a number.
**Tip:** record each scene separately and join the clips in iMovie. One bad take then doesn't cost you the whole video.

---

### Scene 1: The hook (0:00–0:20)
*Screen: the OffPeak screen at rest, price chart visible.*

> "More than 70,000 homes around Chicago pay for electricity by the hour, and almost 22,000 of them drive an EV. The price follows the wholesale market, and on a bad evening it can jump several times over in minutes. Nobody's watching a price chart at 6pm. So I built OffPeak, a home energy autopilot for Alexa+."

### Scene 2: Live price (0:20–0:35)
*Click the mic (or press space) and say:*
> **"What's power costing right now?"**

*Let it answer out loud. The price card appears.*

> "That's the live price from ComEd, the same rate these households actually pay."

### Scene 3: Autopilot (0:35–1:05)
*Say:*
> **"Autopilot tonight."**

*The plan card appears: car, dishwasher, dryer, and the savings. The tiles switch to "scheduled."*

> "It just planned my whole night. The car charges in the cheapest hours and is still ready by 7, and the dishwasher and dryer move off the evening peak. That's the cost, and what I saved versus running it all now."

### Scene 4: Memory and guardrails (1:05–1:25)
*Say:*
> **"I need the car by 6 tomorrow, and charge it to 90 percent."**

> "It saves that and re-plans. My rules carry across every conversation, and it never breaks them."

### Scene 5: The spike, the wow moment (1:25–2:10)
*Click **▶ Replay a price spike**.*

> "Now the real test. I'm replaying an evening price spike. My car just plugged in and the dryer's running."

*Wait. The price chip climbs, the light bar turns red, and OffPeak speaks up on its own. Let the whole announcement play.*

> "I didn't ask it anything. It saw the spike, paused the car and moved charging to later so it's still ready in the morning, held the dryer, eased the thermostat within my limits, and told me exactly what it saved."

*Point at the tiles: Paused, Delayed, Eco.*

### Scene 6: How it works (2:10–2:40)
*Show the README architecture diagram, or the repo in a browser.*

> "Under the hood, there's a self-hosted MCP server over Streamable HTTP with ten tools on live ComEd prices. An Agent Skill defines how OffPeak talks and decides. Claude, through the Strands Agents SDK, runs the agent. A watcher calls the spike check on its own, so the autopilot acts without being asked. The devices are simulated for now, but they're behind one swappable function, and real thermostats and EV chargers are next."

> "OffPeak. Your home, trading power for you."

---

### If something goes wrong mid-recording
- **The agent is slow or errors:** cut the clip and re-record that scene only.
- **Live prices are boring:** that's fine. The spike replay is the dramatic part.
- **Voice input misses a word:** type the question instead. It works the same, and you can say "or just type it."
