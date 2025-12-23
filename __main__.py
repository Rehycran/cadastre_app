# -*- coding: utf-8 -*-
from cadastre_app.uiCTk import App



def main():
    
    def bring_to_front():
        app.deiconify()
        app.lift()
        app.focus_force()
        # small on-top toggle is a common Windows trick
        app.attributes("-topmost", True)
        app.after(100, lambda: app.attributes("-topmost", False))
    
    try:
        import pyi_splash
        has_splash = True
    except Exception:
        has_splash = False

    try:
        # ... init app / création fenêtre ...
        app = App()   # ta fenêtre CTk/Tk
        if has_splash:
            pyi_splash.close()   # <= IMPORTANT : ferme le splash
        
        app.after(0, bring_to_front)
        
        app.run()

    finally:
        # en cas d'exception avant mainloop, éviter splash bloqué
        if has_splash:
            try:
                pyi_splash.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
