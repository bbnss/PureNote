import sqlite3
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.popup import Popup
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.properties import BooleanProperty, StringProperty
from kivy.lang import Builder
from kivy.uix.image import Image


# Setup the database
conn = sqlite3.connect('notes.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS notes
             (note text)''')

# Define RecycleView in KV language
Builder.load_string('''
<SelectableBoxLayout>:
    orientation: 'horizontal'
    Label:
        text: root.display_text
    Button:
        text: 'Delete'
        on_press: root.delete_note()

<SelectableBoxLayout>:
    # Draw a background to indicate selection
    canvas.before:
        Color:
            rgba: (.0, .9, .1, .3) if self.selected else (0, 0, 0, 1)
        Rectangle:
            pos: self.pos
            size: self.size

<RV>:
    viewclass: 'SelectableBoxLayout'
    RecycleBoxLayout:
        default_size: None, dp(56)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'
''')

class SelectableBoxLayout(RecycleDataViewBehavior, BoxLayout):
    """ Add selection support to the BoxLayout """
    text = StringProperty()
    display_text = StringProperty()
    selected = BooleanProperty(False)

    def on_text(self, instance, value):
        self.display_text = value[:15] + ' (' + str(len(value)) + ')'

    def on_touch_down(self, touch):
        if super(SelectableBoxLayout, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos):
            return self.select_note(touch)

    def select_note(self, touch):
        if self.selected:
            return False
        else:
            # Deselect the previously selected note, if there is one
            if App.get_running_app().selected_note is not None:
                App.get_running_app().selected_note.selected = False

            # Select the current note
            self.selected = True
            App.get_running_app().selected_note = self
            App.get_running_app().note_input.text = self.text
            App.get_running_app().note_popup.dismiss()
            return True


    def delete_note(self):
        def delete(btn):
            c.execute("DELETE FROM notes WHERE note=?", (self.text,))
            conn.commit()
            App.get_running_app().note_list.fetch_notes()
            confirm_popup.dismiss()

        confirm_popup = Popup(title='Confirm Delete')
        confirm_layout = BoxLayout(orientation='vertical')
        confirm_layout.add_widget(Label(text=f'Are you sure you want to delete "{self.text}"?'))
        button_layout = BoxLayout(orientation='horizontal')
        button_layout.add_widget(Button(text='Yes', on_press=delete))
        button_layout.add_widget(Button(text='Cancel', on_press=confirm_popup.dismiss))
        confirm_layout.add_widget(button_layout)
        confirm_popup.content = confirm_layout
        confirm_popup.open()

class RV(RecycleView):
    def __init__(self, **kwargs):
        super(RV, self).__init__(**kwargs)
        self.fetch_notes()

    def fetch_notes(self):
        c.execute('SELECT * FROM notes')
        self.data = [{'text': str(row[0])} for row in c.fetchall()]



class NoteApp(App):
    
    def __init__(self, **kwargs):
        super(NoteApp, self).__init__(**kwargs)
        # Initialize the selected note to None
        self.selected_note = None

    def build(self):
        # Main layout
        box = BoxLayout(orientation='vertical')

        top_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=100)
        top_layout.add_widget(Button(text='New Note', font_name='TT.ttf', on_press=self.new_note, size_hint_x=0.25, background_color=(0, 1, 0, 1), color=(1, 1, 0, 1)))
        top_layout.add_widget(Button(text='List', font_name='TT.ttf', on_press=self.show_saved_notes, size_hint_x=0.25, background_color=(0, 0, 0, 1), color=(1, 0, 1, 1)))
        top_layout.add_widget(Button(text='Delete', font_name='TT.ttf', on_press=self.delete_note, size_hint_x=0.25, background_color=(0, 1, 0, 1), color=(1, 1, 0, 1)))
        top_layout.add_widget(Button(text='Save', font_name='TT.ttf', on_press=self.save_note, size_hint_x=0.25, background_color=(0, 0, 0, 1), color=(1, 0, 1, 1)))
        
        box.add_widget(top_layout)

        # Text input for new note
        self.note_input = TextInput(font_name='GS.ttf', background_color=[1, 1, 1, 1])

        box.add_widget(self.note_input)

        # Popup for saved notes
        self.note_list = RV()
        self.note_popup = Popup(title='Saved Notes', content=self.note_list)

        # Add banner image at the bottom
        banner = Image(source='anelli.png', size_hint_y=None, height=100, allow_stretch=True, keep_ratio=False)

        box.add_widget(banner)

        return box

    def new_note(self, instance):
        self.note_input.text = ''

    def save_note(self, instance):
        c.execute("INSERT INTO notes VALUES (?)", (self.note_input.text,))
        conn.commit()
        self.note_list.fetch_notes()

    def delete_note(self, instance):
        def delete(btn):
            c.execute("DELETE FROM notes WHERE note=?", (self.note_input.text,))
            conn.commit()
            self.note_list.fetch_notes()
            self.note_input.text = ''
            confirm_popup.dismiss()

        confirm_popup = Popup(title='Confirm Delete')
        confirm_layout = BoxLayout(orientation='vertical')
        confirm_layout.add_widget(Label(text=f'Are you sure you want to delete "{self.note_input.text}"?'))
        button_layout = BoxLayout(orientation='horizontal')
        button_layout.add_widget(Button(text='Yes', on_press=delete))
        button_layout.add_widget(Button(text='Cancel', on_press=confirm_popup.dismiss))
        confirm_layout.add_widget(button_layout)
        confirm_popup.content = confirm_layout
        confirm_popup.open()

    def show_saved_notes(self, instance):
        self.note_popup.open()

if __name__ == '__main__':
    NoteApp().run()
