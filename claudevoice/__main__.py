import argparse
import asyncio
import os
import sys


def find_piper_model(voice_name: str) -> str:
    """Find or download a Piper voice model."""
    if os.sep in voice_name or "/" in voice_name or ".." in voice_name:
        print(f"Error: Invalid voice name: {voice_name}")
        sys.exit(1)

    data_dir = os.path.expanduser("~/.local/share/piper-voices")
    model_path = os.path.join(data_dir, f"{voice_name}.onnx")

    if os.path.exists(model_path):
        return model_path

    # Check alternate locations
    alt_paths = [
        os.path.join(data_dir, voice_name, f"{voice_name}.onnx"),
        os.path.join("/usr/share/piper-voices", f"{voice_name}.onnx"),
    ]
    for path in alt_paths:
        if os.path.exists(path):
            return path

    print(f"Piper voice model not found: {voice_name}")
    print(f"Searched: {model_path}")
    print()
    print("To download a voice model:")
    print(f"  mkdir -p {data_dir}")
    print(f"  cd {data_dir}")
    print(f"  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx")
    print(f"  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json")
    print()
    print("Or specify a model path with --tts-model /path/to/model.onnx")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="ClaudeVoice - Claude Code for blind users with text-to-speech"
    )
    parser.add_argument(
        "--model", default=None,
        help="Claude model to use (e.g. sonnet, opus)",
    )
    parser.add_argument(
        "--tts-model", default=None,
        help="Path to Piper .onnx model file",
    )
    parser.add_argument(
        "--voice", default="en_US-lessac-medium",
        help="Piper voice name (default: en_US-lessac-medium)",
    )
    parser.add_argument(
        "--no-tools", action="store_true",
        help="Don't announce tool usage",
    )
    parser.add_argument(
        "--no-cost", action="store_true",
        help="Don't announce cost at end",
    )
    parser.add_argument(
        "prompt", nargs="*",
        help="One-shot prompt (otherwise enters interactive mode)",
    )

    args = parser.parse_args()

    # Resolve TTS model path
    if args.tts_model:
        model_path = args.tts_model
        if not os.path.exists(model_path):
            print(f"Error: TTS model not found at {model_path}")
            sys.exit(1)
    else:
        model_path = find_piper_model(args.voice)

    # Create backend
    from claudevoice.claude.subprocess_backend import SubprocessBackend
    backend = SubprocessBackend(model=args.model)

    # Create TTS
    from claudevoice.tts.piper_engine import PiperTTSEngine
    from claudevoice.tts.playback import PlaybackManager
    tts_engine = PiperTTSEngine(model_path=model_path)
    playback = PlaybackManager(tts_engine)

    # Create extractor
    from claudevoice.pipeline.extractor import MessageExtractor
    extractor = MessageExtractor(
        speak_tools=not args.no_tools,
        speak_cost=not args.no_cost,
    )

    # One-shot or interactive mode
    if args.prompt:
        prompt = " ".join(args.prompt)
        asyncio.run(_one_shot(backend, playback, extractor, prompt))
    else:
        from claudevoice.input.keyboard_input import KeyboardInput
        from claudevoice.app import ClaudeVoiceApp
        input_source = KeyboardInput()
        app = ClaudeVoiceApp(backend, playback, input_source, extractor)
        asyncio.run(app.run())


async def _one_shot(backend, playback, extractor, prompt):
    """Run a single prompt, speak the result, and exit."""
    from claudevoice.pipeline.chunker import SentenceChunker
    from claudevoice.claude.messages import MessageKind

    await playback.start()
    chunker = SentenceChunker()

    async for message in backend.send_prompt(prompt):
        text = extractor.extract(message)
        if text is None:
            continue
        if message.kind in (
            MessageKind.TOOL_START, MessageKind.RESULT,
            MessageKind.ERROR, MessageKind.SESSION_INIT,
        ):
            await playback.enqueue(text)
        else:
            for sentence in chunker.feed(text):
                await playback.enqueue(sentence)

    remaining = chunker.flush()
    if remaining:
        await playback.enqueue(remaining)

    await playback.drain()
    await playback.shutdown()
    await backend.close()


if __name__ == "__main__":
    main()
