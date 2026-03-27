import customtkinter as ctk
app = ctk.CTk()
app.geometry("400x240")
button = ctk.CTkButton(app, text="Click Me")
button.pack(padx=20, pady=20)
app.mainloop()
