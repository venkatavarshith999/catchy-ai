package com.catchyai.safety;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(CatchyScreenPlugin.class);
        registerPlugin(CatchySpeechPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
