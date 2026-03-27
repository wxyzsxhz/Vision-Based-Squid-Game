from tkinter import*
def donothing():
    filewin= Toplevel(root)
    button=Button(filewin,text="Do Notihing Button")
    button.pack()
root=Tk()
menubar=Menu(root)
filemenu=Menu(menubar,tearoff=0) 
filemenu.add_command(label="New", command=donothing) 
filemenu.add_command(label="Open", command=donothing)
filemenu.add_command(label="Save", command=donothing)                                                     
filemenu.add_command(label="Save as...", command=donothing)                                                     
filemenu.add_command(label="Close", command=donothing)                                                     
    