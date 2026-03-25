from __future__ import annotations

from schemas.state import TravelState


class HumanAgent:
    def run(self, state: TravelState) -> TravelState:
        try:
            if not state.selected_option:
                state.status = "failed"
                state.errors.append("Human error: no option to review.")
                return state

            print("\n--- HUMAN REVIEW ---")
            print(f"Destination: {state.selected_option.get('city')}")
            print(f"Total price: {state.selected_option.get('total_price')} SEK")
            print(f"Booking link: {state.selected_option.get('booking_link')}")
            print("---------------------\n")

            decision = input("Approve this trip? (yes/no): ").strip().lower()

            if decision == "yes":
                state.human_approved = True
                state.status = "reviewed"
            else:
                state.human_approved = False
                state.status = "failed"

            return state

        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Human error: {str(e)}")
            return state
