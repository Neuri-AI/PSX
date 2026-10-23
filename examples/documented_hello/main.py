from velto import VeltoContext
from velto.ui import psx

class HelloApp(VeltoContext):
    def render(self):
        return psx("""
            <Flex direction="column" gap="12px">
                <Text value="Hello, Velto!" />
            </Flex>
        """)

if __name__ == "__main__":
    HelloApp().run()
